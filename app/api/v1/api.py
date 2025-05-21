from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db import models
from datetime import datetime
from pydantic import BaseModel
import logging
from .auth import router as auth_router
from app.blockchain.web3_client import web3_client

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LoginRequest(BaseModel):
    wallet_address: str
    signature: str
    username: str

class ScheduledMessageRequest(BaseModel):
    recipient_address: str
    message_content: str
    delivery_date: datetime
    user_id: str

api_router = APIRouter()

# Include auth routes
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])

# Auth endpoints
@api_router.post("/auth/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user with wallet signature."""
    # Verify the signature
    message = f"Login to Digital Legacy as {request.username} at {datetime.utcnow().date()}"
    if not web3_client.verify_signature(message, request.signature, request.wallet_address):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Get or create user
    user = db.query(models.User).filter(models.User.wallet_address == request.wallet_address).first()
    if not user:
        user = models.User(
            wallet_address=request.wallet_address,
            username=request.username,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Update last login time and username if changed
        user.last_login = datetime.utcnow()
        user.username = request.username
        db.commit()
    
    return {
        "user_id": user.id,
        "wallet_address": user.wallet_address,
        "username": user.username
    }

# Digital Asset endpoints
@api_router.post("/assets/upload")
async def upload_asset(
    file: UploadFile = File(...),
    title: str = Form(None),
    description: str = Form(None),
    user_id: str = Form(...),
    db: Session = Depends(get_db)
):
    """Upload and encrypt a digital asset."""
    try:
        logger.info(f"Received upload request with user_id: {user_id}")
        
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID is required")
        
        # Convert user_id to integer
        try:
            user_id = int(user_id)
        except ValueError:
            logger.error(f"Invalid user_id format: {user_id}")
            raise HTTPException(status_code=400, detail="Invalid user ID format")
            
        # Verify user exists
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            logger.error(f"User not found with ID: {user_id}")
            raise HTTPException(status_code=404, detail="User not found")
        
        # Generate encryption key
        key = encryption_service.generate_key()
        
        # Create uploads directory if it doesn't exist
        os.makedirs("uploads", exist_ok=True)
        
        # Save and encrypt file
        file_path = f"uploads/{file.filename}"
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        encrypted_path = encryption_service.encrypt_file(file_path, key)
        
        # Create blockchain hash
        content_hash = web3_client.hash_content(str(content))
        blockchain_hash = await web3_client.anchor_hash(content_hash, str(user_id))
        
        # Create database record
        asset = models.DigitalAsset(
            owner_id=user_id,
            title=title or file.filename,
            description=description,
            file_path=encrypted_path,
            asset_type=file.content_type,
            blockchain_hash=blockchain_hash,
            encryption_key=key.decode(),
            asset_metadata={"original_name": file.filename, "content_type": file.content_type}
        )
        
        db.add(asset)
        db.commit()
        db.refresh(asset)
        
        # Clean up the original file
        if os.path.exists(file_path):
            os.remove(file_path)
        
        logger.info(f"Successfully uploaded asset for user {user_id}")
        return {"asset_id": asset.id, "title": asset.title}
    except Exception as e:
        logger.error(f"Error uploading asset: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading asset: {str(e)}")

@api_router.get("/assets/{asset_id}/download")
async def download_asset(
    asset_id: int,
    user_id: int = None,
    db: Session = Depends(get_db)
):
    """Download a digital asset."""
    # Get the asset
    asset = db.query(models.DigitalAsset).filter(
        models.DigitalAsset.id == asset_id,
        models.DigitalAsset.owner_id == user_id
    ).first()
    
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found or not owned by user")
    
    # Decrypt the file
    try:
        decrypted_path = encryption_service.decrypt_file(
            asset.file_path,
            asset.encryption_key.encode()
        )
        
        # Return the file
        return FileResponse(
            decrypted_path,
            media_type=asset.asset_metadata.get('content_type', 'application/octet-stream'),
            filename=asset.asset_metadata.get('original_name', 'downloaded_file')
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to decrypt file: {str(e)}")
    finally:
        # Clean up the decrypted file
        if os.path.exists(decrypted_path):
            os.remove(decrypted_path)

@api_router.get("/assets/list")
async def list_assets(
    user_id: int = None,
    db: Session = Depends(get_db)
):
    """List all assets owned by the user."""
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID is required")
        
    assets = db.query(models.DigitalAsset).filter(
        models.DigitalAsset.owner_id == user_id
    ).all()
    
    return [
        {
            "id": asset.id,
            "title": asset.title,
            "description": asset.description,
            "asset_type": asset.asset_type,
            "created_at": asset.created_at.isoformat() if asset.created_at else None
        }
        for asset in assets
    ]

# Access Rule endpoints
@api_router.post("/access-rules/create")
async def create_access_rule(
    asset_id: int,
    beneficiary_address: str,
    access_type: str,
    trigger_condition: str,
    trigger_date: datetime = None,
    user_id: int = None,
    db: Session = Depends(get_db)
):
    """Create an access rule for a digital asset."""
    # Verify asset ownership
    asset = db.query(models.DigitalAsset).filter(
        models.DigitalAsset.id == asset_id,
        models.DigitalAsset.owner_id == user_id
    ).first()
    
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found or not owned by user")
    
    # Create smart contract for access rule
    conditions = {
        "access_type": access_type,
        "trigger_condition": trigger_condition,
        "trigger_date": trigger_date.isoformat() if trigger_date else None
    }
    
    contract_id = await web3_client.create_access_rule(asset_id, beneficiary_address, conditions)
    
    # Create database record
    rule = models.AccessRule(
        owner_id=user_id,
        digital_asset_id=asset_id,
        beneficiary_address=beneficiary_address,
        access_type=access_type,
        trigger_condition=trigger_condition,
        trigger_date=trigger_date,
        smart_contract_id=contract_id
    )
    
    db.add(rule)
    db.commit()
    db.refresh(rule)
    
    return {"rule_id": rule.id, "contract_id": contract_id}

# Scheduled Message endpoints
@api_router.post("/messages/schedule")
async def schedule_message(
    request: ScheduledMessageRequest,
    db: Session = Depends(get_db)
):
    """Schedule a future message for delivery."""
    try:
        logger.info(f"Received message scheduling request for user: {request.user_id}")
        
        # Validate Ethereum address
        if not Web3.is_address(request.recipient_address):
            logger.warning(f"Invalid recipient address: {request.recipient_address}")
            raise HTTPException(status_code=400, detail="Invalid recipient address")
        
        # Validate delivery date is in the future
        if request.delivery_date <= datetime.utcnow():
            logger.warning(f"Invalid delivery date: {request.delivery_date}")
            raise HTTPException(status_code=400, detail="Delivery date must be in the future")
        
        # Get or create user
        user = db.query(models.User).filter(models.User.wallet_address == request.user_id).first()
        if not user:
            logger.warning(f"User not found: {request.user_id}")
            raise HTTPException(status_code=404, detail="User not found")
        
        logger.info(f"Found user with ID: {user.id}")
        
        try:
            # Generate encryption key
            key = encryption_service.generate_key()
            logger.info("Generated encryption key")
            
            # Encrypt message content
            encrypted_content = encryption_service.encrypt_data(request.message_content.encode(), key)
            logger.info("Encrypted message content")
            
            # Create blockchain hash
            content_hash = web3_client.hash_content(request.message_content)
            blockchain_hash = await web3_client.anchor_hash(content_hash, request.user_id)
            logger.info(f"Created blockchain hash: {blockchain_hash}")
            
            # Create database record
            message = models.ScheduledMessage(
                owner_id=user.id,
                recipient_address=request.recipient_address,
                message_content=encrypted_content,
                delivery_date=request.delivery_date,
                encryption_key=key.decode(),
                blockchain_hash=blockchain_hash
            )
            
            db.add(message)
            db.commit()
            db.refresh(message)
            logger.info(f"Created scheduled message with ID: {message.id}")
            
            return {
                "message_id": message.id,
                "delivery_date": message.delivery_date.isoformat(),
                "recipient_address": message.recipient_address
            }
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in schedule_message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@api_router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"} 