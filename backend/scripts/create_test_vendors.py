import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.db.base import User, Vendor, Stall, Base
from app.models.user import UserRole
from app.core.security import get_password_hash
from app.services.qr.service import issue_for_stall
import random

def create_vendors():
    db = SessionLocal()
    try:
        password = get_password_hash("password123")
        for i in range(1, 11):
            email = f"testvendor{i}@example.com"
            user = db.query(User).filter(User.email == email).first()
            if not user:
                user = User(
                    email=email,
                    hashed_password=password,
                    role=UserRole.VENDOR,
                    full_name=f"Test Vendor {i}"
                )
                db.add(user)
                db.flush()

                vendor = Vendor(
                    user_id=user.id,
                    phone_number=f"99999999{i:02d}",
                    preferred_language="en"
                )
                db.add(vendor)
                db.flush()

                lat = random.uniform(18.9, 19.3)
                lng = random.uniform(72.8, 73.0)
                
                stall = Stall(
                    vendor_id=vendor.id,
                    name=f"Test Stall {i}",
                    food_category="Street Food",
                    address=f"Mumbai Test Location {i}",
                    latitude=lat,
                    longitude=lng
                )
                db.add(stall)
                db.flush()
                
                qr_code = issue_for_stall(db, stall)
                
                print(f"Created vendor {email} with stall {stall.name} at {lat}, {lng}, code: {qr_code.code}")
            else:
                # User exists, check if they have a stall with a QR code
                vendor = db.query(Vendor).filter(Vendor.user_id == user.id).first()
                if vendor:
                    stall = db.query(Stall).filter(Stall.vendor_id == vendor.id).first()
                    if stall:
                        if not stall.qr_code_id:
                            qr_code = issue_for_stall(db, stall)
                            print(f"Issued QR code {qr_code.code} for existing stall {stall.name}")
        
        db.commit()
        print("Successfully ensured 10 test vendors have stalls with QR codes.")
    except Exception as e:
        db.rollback()
        print(f"Error creating vendors: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_vendors()
