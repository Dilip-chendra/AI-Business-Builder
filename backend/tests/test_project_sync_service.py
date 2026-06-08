from types import SimpleNamespace

from app.services.project_sync_service import ProjectSyncService


def _business():
    return SimpleNamespace(
        id="sync-test-business",
        name="Sync Test",
        niche="testing",
        description="A test business",
        target_audience="testers",
        monetization_model="subscription",
        brand_tone="clear",
        headline="Original headline",
        subheading="Original subheading",
        product_pitch="Original pitch",
        cta_text="Start",
        seo_title="SEO",
        seo_description="SEO description",
        page_content={},
    )


def test_ensure_scaffold_does_not_overwrite_existing_workspace_edits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    service = ProjectSyncService(_business())

    service.ensure_scaffold()
    hero_path = tmp_path / "workspace" / "sync-test-business" / "components" / "Hero.tsx"
    edited = "export function Hero() { return <div>Edited by AI</div>; }\n"
    hero_path.write_text(edited, encoding="utf-8")

    service.ensure_scaffold()

    assert hero_path.read_text(encoding="utf-8") == edited


def test_sync_business_profile_still_updates_generated_business_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    business = _business()
    service = ProjectSyncService(business)
    service.ensure_scaffold()

    business.headline = "Updated headline"
    updated = service.sync_business_profile()

    assert "data/business.json" in updated
    assert "Updated headline" in (tmp_path / "workspace" / "sync-test-business" / "data" / "business.json").read_text(encoding="utf-8")
