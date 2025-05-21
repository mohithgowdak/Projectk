from fastapi import APIRouter, Depends, HTTPException, status, Security
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db import models
from app.services.email_service import email_service
from pydantic import BaseModel, EmailStr, validator, constr
from passlib.context import CryptContext
from datetime import datetime, timedelta
import jwt
from typing import Optional, Dict, Any
import logging
import os
from dotenv import load_dotenv
import random
import string
import web3
from eth_account.messages import encode_defunct
from web3 import Web3

# Initialize router
router = APIRouter()

# Load environment variables
load_dotenv()

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(os.getenv("ETHEREUM_RPC_URL", "http://localhost:8545")))

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
REFRESH_SECRET_KEY = os.getenv("REFRESH_SECRET_KEY", "your-refresh-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
MAX_LOGIN_ATTEMPTS = 5
LOGIN_ATTEMPT_WINDOW = 15  # minutes
OTP_EXPIRY_MINUTES = 5

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def generate_user_id(db: Session) -> str:
    """Generate a unique user ID in the format ude-XXXXXX"""
    while True:
        random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        user_id = f"ude-{random_part}"
        # Check if ID exists in database
        if not db.query(models.User).filter(models.User.user_id == user_id).first():
            return user_id

def verify_ethereum_signature(message: str, signature: str, address: str) -> bool:
    """Verify Ethereum signature"""
    try:
        message_hash = encode_defunct(text=message)
        recovered_address = w3.eth.account.recover_message(message_hash, signature=signature)
        return recovered_address.lower() == address.lower()
    except Exception as e:
        logger.error(f"Error verifying signature: {str(e)}")
        return False

class UserProfileBase(BaseModel):
    username: constr(min_length=3, max_length=50)
    full_name: constr(min_length=2, max_length=100)
    email: EmailStr
    phone_number: constr(min_length=10, max_length=15)
    date_of_birth: datetime
    address: constr(min_length=5, max_length=200)
    bio: constr(min_length=10, max_length=500)

class SignupRequest(UserProfileBase):
    wallet_address: Optional[str] = None
    wallet_signature: Optional[str] = None
    email_otp: Optional[str] = None

    @validator('wallet_address')
    def validate_wallet_address(cls, v):
        if v and not w3.is_address(v):
            raise ValueError('Invalid Ethereum address')
        return v

class LoginRequest(BaseModel):
    email: EmailStr
    otp: Optional[str] = None
    wallet_address: Optional[str] = None
    wallet_signature: Optional[str] = None

    @validator('wallet_address')
    def validate_wallet_address(cls, v):
        if v and not w3.is_address(v):
            raise ValueError('Invalid Ethereum address')
        return v

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user_id: str

class TokenData(BaseModel):
    user_id: str
    email: str

class RefreshToken(BaseModel):
    refresh_token: str

class OTPRequest(BaseModel):
    email: EmailStr

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, REFRESH_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(user_id=user_id, email=payload.get("email"))
    except jwt.PyJWTError:
        raise credentials_exception
    
    user = db.query(models.User).filter(models.User.user_id == token_data.user_id).first()
    if user is None:
        raise credentials_exception
    return user

@router.post("/signup")
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """Register a new user with required profile information and either wallet or email verification."""
    
    # Check if email already exists
    if db.query(models.User).filter(models.User.email == request.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if wallet address is already linked
    if request.wallet_address and db.query(models.User).filter(
        models.User.wallet_address == request.wallet_address.lower()
    ).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wallet address already linked to another account"
        )
    
    # Verify either wallet signature or email OTP
    if request.wallet_address and request.wallet_signature:
        if not verify_ethereum_signature(
            f"Sign this message to verify your wallet ownership for {request.email}",
            request.wallet_signature,
            request.wallet_address
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid wallet signature"
            )
    elif request.email_otp:
        if not email_service.verify_otp(request.email, request.email_otp):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OTP"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either wallet signature or email OTP is required"
        )
    
    # Generate unique user ID
    user_id = generate_user_id(db)
    
    # Create new user
    user = models.User(
        user_id=user_id,
        email=request.email,
        username=request.username,
        full_name=request.full_name,
        phone_number=request.phone_number,
        date_of_birth=request.date_of_birth,
        address=request.address,
        bio=request.bio,
        wallet_address=request.wallet_address.lower() if request.wallet_address else None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Generate tokens
    access_token = create_access_token(
        data={"sub": user.user_id, "email": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = create_refresh_token(data={"sub": user.user_id, "email": user.email})
    
    return {
        "message": "User registered successfully",
        "user_id": user.user_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Login with either email OTP or MetaMask wallet."""
    
    user = None
    
    # Find user by email
    if request.email:
        user = db.query(models.User).filter(models.User.email == request.email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found. Please sign up first."
            )
    
    # Verify login method
    if request.wallet_address and request.wallet_signature:
        if not user or user.wallet_address != request.wallet_address.lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid wallet address"
            )
        
        if not verify_ethereum_signature(
            f"Sign this message to login to your account {user.email}",
            request.wallet_signature,
            request.wallet_address
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid wallet signature"
            )
    elif request.otp:
        if not email_service.verify_otp(request.email, request.otp):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired OTP"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either wallet signature or OTP is required"
        )
    
    # Update last login time
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Generate tokens
    access_token = create_access_token(
        data={"sub": user.user_id, "email": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = create_refresh_token(data={"sub": user.user_id, "email": user.email})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": user.user_id
    }

@router.post("/request-otp")
async def request_otp(request: OTPRequest, db: Session = Depends(get_db)):
    """Request OTP for login or signup"""
    try:
        # Check if user exists for login
        user = db.query(models.User).filter(models.User.email == request.email).first()
        
        if not user:
            # For new users, just send OTP
            if email_service.send_otp(request.email):
                return {"message": "OTP sent successfully"}
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to send OTP"
                )
        
        # For existing users, check if they have a wallet
        if not user.wallet_address:
            if email_service.send_otp(request.email):
                return {"message": "OTP sent successfully"}
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to send OTP"
                )
        
        return {
            "message": "OTP sent successfully",
            "has_wallet": True,
            "wallet_address": user.wallet_address
        }
    except Exception as e:
        logger.error(f"Error in request_otp: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your request"
        )

class OTPVerifyRequest(BaseModel):
    email: EmailStr
    otp: str

@router.post("/verify-otp")
async def verify_otp(request: OTPVerifyRequest, db: Session = Depends(get_db)):
    """Verify OTP for login"""
    try:
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
        
        # Update last login time
        user.last_login = datetime.utcnow()
        db.commit()
        
        # Generate tokens
        access_token = create_access_token(
            data={"sub": user.user_id, "email": user.email},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        refresh_token = create_refresh_token(data={"sub": user.user_id, "email": user.email})
        
        return {
            "message": "OTP verified successfully",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user_id": user.user_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in verify_otp: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while verifying OTP"
        )

@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token_data: RefreshToken,
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(refresh_token_data.refresh_token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        if user_id is None or email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    access_token = create_access_token(
        data={"sub": user.user_id, "email": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    new_refresh_token = create_refresh_token(data={"sub": user.user_id, "email": user.email})
    
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "user_id": user.user_id
    }

@router.post("/logout")
async def logout(current_user: models.User = Depends(get_current_user)):
    """Logout user by invalidating their tokens."""
    return {"message": "Successfully logged out"} 