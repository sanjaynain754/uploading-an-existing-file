"""Run this once to create the database tables."""
import asyncio
from app.database import init_db

if __name__ == "__main__":
    asyncio.run(init_db())
    print("✓ Database initialized")
