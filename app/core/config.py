from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
logger.info("Loading environment variables...")

class Settings(BaseSettings):
    APP_NAME: str = "Digital Legacy Manager"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = "sqlite:///./digital_legacy.db"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-here")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Blockchain
    POLYGON_RPC_URL: str = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")
    POLYGON_CHAIN_ID: int = 137
    CONTRACT_ADDRESS: Optional[str] = None
    
    # Storage
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_FILE_TYPES: str = "image/*,video/*,application/pdf,text/*"
    
    # Google Cloud Storage
    GOOGLE_CLOUD_PROJECT: Optional[str] = None
    GOOGLE_CLOUD_BUCKET: Optional[str] = None
    
    # Email settings
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.info("Email Configuration:")
        logger.info(f"SMTP_HOST: {self.SMTP_HOST}")
        logger.info(f"SMTP_PORT: {self.SMTP_PORT}")
        logger.info(f"SMTP_USERNAME: {self.SMTP_USERNAME}")
        logger.info(f"SMTP_PASSWORD: {'*' * len(self.SMTP_PASSWORD) if self.SMTP_PASSWORD else 'Not set'}")
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings() 