import asyncio
import sys
import os
import uuid

# Add project root to path so backend module is found
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.core.config import Settings
from backend.core.database import create_engine, create_session_factory
from backend.models.user import User
from backend.services.auth_service import hash_password

settings = Settings()
engine = create_engine(settings.database_url)
SessionLocal = create_session_factory(engine)

from sqlalchemy import select

async def create_user(email: str, password: str, display_name: str):
    async with SessionLocal() as session:
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user:
            print(f"User {email} already exists. Updating password and verification status...")
            user.password_hash = hash_password(password)
            user.email_verified = True
        else:
            print(f"User {email} not found. Creating new...")
            user = User(
                external_id=f"local:{uuid.uuid4()}",
                email=email,
                display_name=display_name,
                password_hash=hash_password(password),
                email_verified=True,
                auth_provider="local",
            )
            session.add(user)
            
        try:
            await session.commit()
            print(f"Success! Test user ready:")
            print(f"Email: {email}")
            print(f"Password: {password}")
        except Exception as e:
            await session.rollback()
            print(f"Error: {e}")

if __name__ == "__main__":
    # Create a verified test account
    asyncio.run(create_user("test@example.com", "Password123", "Test User"))
