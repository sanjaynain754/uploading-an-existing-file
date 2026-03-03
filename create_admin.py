"""
पहली बार Admin बनाने के लिए यह script चलाएं।
Usage: python scripts/create_admin.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import get_settings
from app.models import Base, AdminUser
from app.services.auth_service import create_admin, get_admin_by_email

settings = get_settings()
_sync_url = settings.database_url.replace("+aiosqlite", "")
engine = create_engine(_sync_url, connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def main():
    print("=" * 40)
    print("   🔐 Admin Account Setup")
    print("=" * 40)

    with Session() as db:
        # Check if admin exists
        existing = db.query(AdminUser).first()
        if existing:
            print(f"⚠️  Admin पहले से है: {existing.email}")
            print("नया admin बनाने के लिए पुराना delete करें।")
            return

        email    = input("📧 Email: ").strip()
        password = input("🔑 Password: ").strip()
        name     = input("👤 Name (Admin): ").strip() or "Admin"

        if len(password) < 6:
            print("❌ Password कम से कम 6 characters का होना चाहिए!")
            return

        admin = create_admin(db, email, password, name)
        print(f"\n✅ Admin बन गया!")
        print(f"   Email: {admin.email}")
        print(f"   Name:  {admin.name}")
        print(f"\n🚀 Login करें: POST /admin/login")
        print(f'   {{"email": "{email}", "password": "****"}}')

if __name__ == "__main__":
    main()
