from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db import models
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter()

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    address: Optional[str] = None
    bio: Optional[str] = None
    profile_picture: Optional[str] = None

@router.get("/{user_id}/profile")
async def get_profile(user_id: int, db: Session = Depends(get_db)):
    """Get user profile"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "phone_number": user.phone_number,
        "date_of_birth": user.date_of_birth,
        "address": user.address,
        "bio": user.bio,
        "profile_picture": user.profile_picture,
        "wallet_address": user.wallet_address
    }

@router.put("/{user_id}/profile")
async def update_profile(user_id: int, profile: ProfileUpdate, db: Session = Depends(get_db)):
    """Update user profile"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update profile fields
    for field, value in profile.dict(exclude_unset=True).items():
        setattr(user, field, value)
    
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "phone_number": user.phone_number,
        "date_of_birth": user.date_of_birth,
        "address": user.address,
        "bio": user.bio,
        "profile_picture": user.profile_picture,
        "wallet_address": user.wallet_address
    } 