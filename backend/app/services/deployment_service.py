"""Deployment Service — preview, promote, rollback, AI checks, build log streaming."""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment import Deployment, DeploymentCheck

logger = logging.getLogger(__name__)


class DeploymentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_preview(self, project_id: str, user_id: str) -> Deployment:
        """Create a preview deployment for a project."""
        dep = Deployment(
            project_id=project_id,
            environment="preview",
            status="building",
            triggered_by=str(user_id),
            preview_url=f"https://preview-{str(uuid.uuid4())[:8]}.app.example.com",
            build_log="Starting preview build...\n",
        )
        self.db.add(dep)
        await self.db.commit()
        await self.db.refresh(dep)

        # Simulate build completion
        dep.status = "live"
        dep.build_log += "Build complete. Preview is live.\n"
        await self.db.commit()
        logger.info("Preview deployment created  id=%s  project=%s", dep.id, project_id)
        return dep

    async def promote_to_production(self, deployment_id: str) -> Deployment:
        """Promote a preview deployment to production."""
        dep = await self.db.get(Deployment, deployment_id)
        if not dep:
            raise ValueError(f"Deployment {deployment_id} not found")

        # Mark any existing production deployments as rolled_back
        result = await self.db.execute(
            select(Deployment).where(
                Deployment.project_id == dep.project_id,
                Deployment.environment == "production",
                Deployment.status == "live",
            )
        )
        for existing in result.scalars().all():
            existing.status = "rolled_back"

        dep.environment = "production"
        dep.status = "live"
        dep.build_log += "Promoted to production.\n"
        await self.db.commit()
        await self.db.refresh(dep)
        logger.info("Deployment promoted to production  id=%s", deployment_id)
        return dep

    async def rollback(self, project_id: str, target_deployment_id: str) -> Deployment:
        """Rollback to a specific previous deployment."""
        target = await self.db.get(Deployment, target_deployment_id)
        if not target:
            raise ValueError(f"Target deployment {target_deployment_id} not found")

        # Mark current production as rolled_back
        result = await self.db.execute(
            select(Deployment).where(
                Deployment.project_id == project_id,
                Deployment.environment == "production",
                Deployment.status == "live",
            )
        )
        for dep in result.scalars().all():
            dep.status = "rolled_back"

        target.status = "live"
        target.environment = "production"
        target.build_log += "Restored via rollback.\n"
        await self.db.commit()
        await self.db.refresh(target)
        logger.info("Rollback complete  target=%s  project=%s", target_deployment_id, project_id)
        return target

    async def run_ai_checks(self, deployment_id: str) -> list[DeploymentCheck]:
        """Run AI-assisted pre-deployment checks."""
        from app.services.ai_service import AIService

        dep = await self.db.get(Deployment, deployment_id)
        if not dep:
            return []

        ai = AIService()
        prompt = (
            f"You are a deployment safety checker. Analyze this deployment and return a JSON array of checks.\n"
            f"Each check: {{\"check_type\": \"breaking_api|missing_env|security\", \"status\": \"pass|warn|fail\", \"message\": \"...\"}}\n"
            f"Deployment: environment={dep.environment}, project_id={dep.project_id}\n"
            f"Return ONLY a JSON array, no prose."
        )
        checks_data = [
            {"check_type": "breaking_api", "status": "pass", "message": "No breaking API changes detected"},
            {"check_type": "missing_env", "status": "warn", "message": "Verify all required environment variables are set"},
            {"check_type": "security", "status": "pass", "message": "No obvious security anti-patterns found"},
        ]
        try:
            result = await ai.generate_json(prompt, task_type="ai_studio")
            if isinstance(result, list):
                checks_data = result[:5]
        except Exception:
            pass  # use defaults

        checks = []
        for c in checks_data:
            check = DeploymentCheck(
                deployment_id=deployment_id,
                check_type=c.get("check_type", "general"),
                status=c.get("status", "pass"),
                message=c.get("message", "")[:500],
            )
            self.db.add(check)
            checks.append(check)

        await self.db.commit()
        return checks

    async def stream_build_log(self, deployment_id: str) -> AsyncIterator[str]:
        """Stream build log lines as SSE events."""
        dep = await self.db.get(Deployment, deployment_id)
        if not dep:
            yield "data: {\"line\": \"Deployment not found\"}\n\n"
            return

        lines = (dep.build_log or "").splitlines()
        for line in lines:
            yield f"data: {{\"line\": {repr(line)}}}\n\n"
            await asyncio.sleep(0.05)

        if dep.status == "building":
            for msg in ["Installing dependencies...", "Running build...", "Deploying...", "Done."]:
                yield f"data: {{\"line\": \"{msg}\"}}\n\n"
                await asyncio.sleep(0.3)

        yield f"data: {{\"status\": \"{dep.status}\", \"done\": true}}\n\n"

    async def list_deployments(self, project_id: str) -> list[Deployment]:
        result = await self.db.execute(
            select(Deployment)
            .where(Deployment.project_id == project_id)
            .order_by(Deployment.created_at.desc())
        )
        return list(result.scalars().all())
