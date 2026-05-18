import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from uuid import uuid4

# Set up environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select
from app.db.session import async_session
from app.models.business import Business
from app.models.scheduled_post import ScheduledPost
from app.models.marketing import MarketingCampaign
from app.services.marketing_service import MarketingService

async def run_test():
    async with async_session() as session:
        # Get or create a business
        result = await session.execute(select(Business))
        business = result.scalars().first()
        if not business:
            print("Creating dummy business...")
            business = Business(
                id=str(uuid4()),
                user_id=str(uuid4()),
                name="Test Business",
                niche="Testing",
                target_audience="Developers",
                status="active"
            )
            session.add(business)
            await session.commit()
            await session.refresh(business)
        
        print(f"Using business {business.id}")
        
        # Create a dummy campaign
        campaign = MarketingCampaign(
            business_id=business.id,
            campaign_type="social",
            name="End-to-End Test Campaign",
            status="approved",
            content={"posts": [{"text": "Hello world from the scheduling background task!"}]},
            targeting={"platform": "twitter"},
            metrics={}
        )
        session.add(campaign)
        await session.commit()
        await session.refresh(campaign)
        print(f"Created campaign {campaign.id}")
        
        # Create a scheduled post that is due RIGHT NOW
        due_date = datetime.now(timezone.utc) - timedelta(minutes=1)
        post = ScheduledPost(
            campaign_id=campaign.id,
            business_id=business.id,
            platform="twitter",
            content_json=campaign.content,
            scheduled_at_utc=due_date,
            timezone="UTC",
            status="pending"
        )
        session.add(post)
        await session.commit()
        await session.refresh(post)
        print(f"Created ScheduledPost {post.id} due at {due_date}")

if __name__ == "__main__":
    asyncio.run(run_test())
