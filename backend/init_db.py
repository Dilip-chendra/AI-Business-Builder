import asyncio
from app.db.session import engine
from app.models.base import Base

# Import all models so they are registered with Base.metadata
from app.models.user import User
from app.models.business import Business
from app.models.product import Product
from app.models.order import Order
from app.models.analytics import AnalyticsEvent
from app.models.agent import AgentLog, AgentTask
from app.models.experiment import Experiment, LandingVariant, ExperimentAssignment

async def init_db():
    async with engine.begin() as conn:
        print("Creating tables...")
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        print("Tables created successfully.")

if __name__ == "__main__":
    asyncio.run(init_db())
