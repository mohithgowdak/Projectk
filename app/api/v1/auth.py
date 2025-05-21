from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db import models
from app.services.email_service import email_service
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from datetime import datetime, timedelta
import jwt
from typing import Optional
import logging

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = "your-secret-key-here"  # Change this to a secure secret key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailSignupRequest(BaseModel):
    email: EmailStr
    username: Optional[str] = None
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    address: Optional[str] = None
    bio: Optional[str] = None

class EmailLoginRequest(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class OTPRequest(BaseModel):
    email: EmailStr
    username: Optional[str] = None
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    address: Optional[str] = None
    bio: Optional[str] = None

class OTPVerify(BaseModel):
    email: EmailStr
    otp: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    address: Optional[str] = None
    bio: Optional[str] = None

class WalletConnectRequest(BaseModel):
    wallet_address: str
    signature: str
    email: Optional[EmailStr] = None

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

router = APIRouter()

@router.post("/email-signup")
async def email_signup(request: EmailSignupRequest, db: Session = Depends(get_db)):
    """Register a new user with email and password."""
    # Check if email already exists
    if db.query(models.User).filter(models.User.email == request.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    hashed_password = get_password_hash(request.password)
    user = models.User(
        email=request.email,
        password_hash=hashed_password,
        wallet_address=None,  # Can be added later
        is_active=True
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return {"message": "User registered successfully", "user_id": user.id}

@router.post("/email-login")
async def email_login(request: EmailLoginRequest, db: Session = Depends(get_db)):
    """Login with email and password."""
    # Find user by email
    user = db.query(models.User).filter(models.User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Verify password
    if not verify_password(request.password, user.password_hash or ""):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email
    }

@router.post("/request-otp")
async def request_otp(request: OTPRequest, db: Session = Depends(get_db)):
    """Request OTP for login or signup"""
    logger.info(f"Requesting OTP for email: {request.email}")
    
    # Check if user exists
    user = db.query(models.User).filter(models.User.email == request.email).first()
    
    if not user:
        # For new users, store the profile data temporarily
        user = models.User(
            email=request.email,
            username=request.username,
            full_name=request.full_name,
            phone_number=request.phone_number,
            date_of_birth=request.date_of_birth,
            address=request.address,
            bio=request.bio,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    # Send OTP
    if email_service.send_otp(request.email):
        return {"message": "OTP sent successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP"
        )

@router.post("/verify-otp")
async def verify_otp(request: OTPVerify, db: Session = Depends(get_db)):
    """Verify OTP for login"""
    logger.info(f"Verifying OTP for email: {request.email}")
    
    user = db.query(models.User).filter(models.User.email == request.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not email_service.verify_otp(request.email, request.otp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )
    
    # Update last login time and profile data if provided
    user.last_login = datetime.utcnow()
    if request.username:
        user.username = request.username
    if request.full_name:
        user.full_name = request.full_name
    if request.phone_number:
        user.phone_number = request.phone_number
    if request.date_of_birth:
        user.date_of_birth = request.date_of_birth
    if request.address:
        user.address = request.address
    if request.bio:
        user.bio = request.bio
    
    db.commit()
    db.refresh(user)
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires
    )
    
    return {
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
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
    }

@router.post("/verify-signup-otp")
async def verify_signup_otp(request: OTPVerify, db: Session = Depends(get_db)):
    """Verify OTP for signup"""
    # Check if user already exists
    user = db.query(models.User).filter(models.User.email == request.email).first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    if not email_service.verify_otp(request.email, request.otp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )
    
    # Create new user with profile information
    new_user = models.User(
        email=request.email,
        username=request.username,
        full_name=request.full_name,
        phone_number=request.phone_number,
        date_of_birth=request.date_of_birth,
        address=request.address,
        bio=request.bio,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {
        "message": "Account created successfully",
        "user": {
            "id": new_user.id,
            "email": new_user.email,
            "username": new_user.username,
            "full_name": new_user.full_name,
            "phone_number": new_user.phone_number,
            "date_of_birth": new_user.date_of_birth,
            "address": new_user.address,
            "bio": new_user.bio,
            "profile_picture": new_user.profile_picture
        }
    }

@router.post("/connect-wallet")
async def connect_wallet(request: WalletConnectRequest, db: Session = Depends(get_db)):
    """Connect wallet to existing account or create new account"""
    logger.info(f"Connecting wallet: {request.wallet_address}")
    
    # Check if wallet is already connected to another account
    existing_wallet = db.query(models.User).filter(
        models.User.wallet_address == request.wallet_address
    ).first()
    
    # Only perform this check if email is provided (i.e., when connecting, not logging in)
    if request.email and existing_wallet and existing_wallet.email != request.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wallet already connected to another account"
        )
    
    # If email is provided, connect wallet to existing account
    if request.email:
        user = db.query(models.User).filter(models.User.email == request.email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update user's wallet address
        user.wallet_address = request.wallet_address
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.email},
            expires_delta=access_token_expires
        )
        
        return {
            "message": "Wallet connected successfully",
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
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
        }
    
    # If no email provided, check if wallet exists
    if existing_wallet:
        # Create access token for existing wallet user
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": existing_wallet.email},
            expires_delta=access_token_expires
        )
        
        return {
            "message": "Login successful",
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": existing_wallet.id,
                "email": existing_wallet.email,
                "username": existing_wallet.username,
                "full_name": existing_wallet.full_name,
                "phone_number": existing_wallet.phone_number,
                "date_of_birth": existing_wallet.date_of_birth,
                "address": existing_wallet.address,
                "bio": existing_wallet.bio,
                "profile_picture": existing_wallet.profile_picture,
                "wallet_address": existing_wallet.wallet_address
            }
        }
    
    # If wallet doesn't exist, create new account
    new_user = models.User(
        wallet_address=request.wallet_address,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Create access token for new user
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": new_user.email},
        expires_delta=access_token_expires
    )
    
    return {
        "message": "Account created successfully",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": new_user.id,
            "email": new_user.email,
            "username": new_user.username,
            "full_name": new_user.full_name,
            "phone_number": new_user.phone_number,
            "date_of_birth": new_user.date_of_birth,
            "address": new_user.address,
            "bio": new_user.bio,
            "profile_picture": new_user.profile_picture,
            "wallet_address": new_user.wallet_address
        }
    } 