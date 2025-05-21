from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.encryption import encryption_service
from app.blockchain.web3_client import web3_client
from app.db import models
from datetime import datetime
import os
import logging
import mimetypes
import shutil
from io import BytesIO

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/upload")
async def upload_asset(
    file: UploadFile = File(...),
    title: str = Form(None),
    description: str = Form(None),
    user_id: str = Form(...),
    db: Session = Depends(get_db)
):
    """Upload and encrypt a digital asset."""
    try:
        logger.info(f"Received upload request for user {user_id}")
        
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
        
        # Create uploads directory if it doesn't exist
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        
        # Get original filename and ensure it has an extension
        original_filename = file.filename
        if not os.path.splitext(original_filename)[1]:
            # If no extension, try to determine it from content type
            ext = mimetypes.guess_extension(file.content_type)
            if ext:
                original_filename = f"{original_filename}{ext}"
        
        # Generate a unique filename while preserving extension
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name, ext = os.path.splitext(original_filename)
        safe_filename = f"{timestamp}_{name}{ext}"
        file_path = os.path.join(upload_dir, safe_filename)
        
        # Save the uploaded file
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            logger.error(f"Error saving uploaded file: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to save uploaded file")
        finally:
            file.file.close()
        
        # Encrypt the file
        try:
            encrypted_path, encryption_key = encryption_service.encrypt_file(file_path)
        except Exception as e:
            logger.error(f"Error encrypting file: {str(e)}")
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(status_code=500, detail="Failed to encrypt file")
        
        # Get file metadata
        file_size = os.path.getsize(file_path)
        content_type = file.content_type or mimetypes.guess_type(original_filename)[0] or 'application/octet-stream'
        
        # Create blockchain hash
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            content_hash = web3_client.hash_content(str(content))
            blockchain_hash = await web3_client.anchor_hash(content_hash, str(user_id))
        except Exception as e:
            logger.error(f"Error creating blockchain hash: {str(e)}")
            blockchain_hash = None
        
        # Create database record
        asset = models.DigitalAsset(
            owner_id=user_id,
            title=title or original_filename,
            description=description,
            file_path=encrypted_path,
            asset_type=content_type,
            blockchain_hash=blockchain_hash,
            encryption_key=encryption_key.decode(),
            asset_metadata={
                "original_name": original_filename,
                "content_type": content_type,
                "file_size": file_size,
                "upload_date": datetime.now().isoformat(),
                "file_extension": os.path.splitext(original_filename)[1]
            }
        )
        
        try:
            db.add(asset)
            db.commit()
            db.refresh(asset)
        except Exception as e:
            logger.error(f"Error saving to database: {str(e)}")
            if os.path.exists(encrypted_path):
                os.remove(encrypted_path)
            raise HTTPException(status_code=500, detail="Failed to save asset to database")
        
        # Clean up the original file
        if os.path.exists(file_path):
            os.remove(file_path)
        
        logger.info(f"Successfully uploaded asset {asset.id} for user {user_id}")
        return {
            "asset_id": asset.id,
            "title": asset.title,
            "file_size": file_size,
            "content_type": content_type,
            "original_filename": original_filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during upload: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")

@router.get("/list")
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

@router.get("/{asset_id}/download")
async def download_asset(
    asset_id: int,
    user_id: int = None,
    db: Session = Depends(get_db)
):
    """Download a digital asset."""
    try:
        logger.info(f"Processing download request for asset {asset_id} and user_id {user_id}")
        
        if not user_id:
            logger.error("user_id parameter is required")
            raise HTTPException(
                status_code=400, 
                detail="user_id parameter is required. Please add ?user_id=YOUR_USER_ID to the URL"
            )
        
        # Get the asset
        asset = db.query(models.DigitalAsset).filter(
            models.DigitalAsset.id == asset_id,
            models.DigitalAsset.owner_id == user_id
        ).first()
        
        if not asset:
            logger.error(f"Asset not found: asset_id={asset_id}, user_id={user_id}")
            raise HTTPException(
                status_code=404, 
                detail=f"Asset not found or not owned by user. Please verify asset_id={asset_id} and user_id={user_id}"
            )
        
        logger.info(f"Found asset: {asset.id}, file_path: {asset.file_path}")
        
        # Verify file exists
        if not os.path.exists(asset.file_path):
            logger.error(f"Asset file not found at path: {asset.file_path}")
            raise HTTPException(
                status_code=404, 
                detail=f"Asset file not found at path: {asset.file_path}"
            )
        
        # Decrypt the file
        try:
            decrypted_path = encryption_service.decrypt_file(
                asset.file_path,
                asset.encryption_key.encode()
            )
            logger.info(f"Successfully decrypted file to: {decrypted_path}")
        except Exception as e:
            logger.error(f"Error decrypting file: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to decrypt file")
        
        try:
            # Get file metadata
            content_type = asset.asset_metadata.get('content_type') or asset.asset_type or 'application/octet-stream'
            original_filename = asset.asset_metadata.get('original_name', 'downloaded_file')

            # Ensure filename has correct extension
            if not os.path.splitext(original_filename)[1]:
                ext = mimetypes.guess_extension(content_type) or ''
                original_filename += ext

            logger.info(f"Decrypted file path: {decrypted_path}")
            logger.info(f"Original filename: {original_filename}")
            logger.info(f"Content type: {content_type}")

            # Read the decrypted file
            with open(decrypted_path, 'rb') as f:
                file_content = f.read()

            # Send file using StreamingResponse
            return StreamingResponse(
                BytesIO(file_content),
                media_type=content_type,
                headers={
                    "Content-Disposition": f'attachment; filename="{original_filename}"'
                }
            )

        except Exception as e:
            logger.error(f"Error preparing file response: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to prepare file for download")

        finally:
            # Clean up the decrypted file
            if os.path.exists(decrypted_path):
                os.remove(decrypted_path)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during download: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
