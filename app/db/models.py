from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base, TimestampMixin
from datetime import datetime
import random
import string

def generate_user_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(8), unique=True, index=True, nullable=False, default=generate_user_id)
    username = Column(String, unique=True, index=True, nullable=True)
    wallet_address = Column(String, unique=True, index=True, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(String, nullable=True)
    name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    # Profile information
    full_name = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    date_of_birth = Column(DateTime(timezone=True), nullable=True)
    address = Column(String, nullable=True)
    profile_picture = Column(String, nullable=True)
    bio = Column(String, nullable=True)
    
    # Relationships
    digital_assets = relationship("DigitalAsset", back_populates="owner")
    access_rules = relationship("AccessRule", back_populates="owner")
    scheduled_messages = relationship("ScheduledMessage", back_populates="owner")

class DigitalAsset(Base, TimestampMixin):
    __tablename__ = "digital_assets"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    asset_type = Column(String)  # photo, video, document, text
    title = Column(String)
    description = Column(Text)
    file_path = Column(String)
    blockchain_hash = Column(String)
    asset_metadata = Column(JSON)
    encryption_key = Column(String)
    
    # Relationships
    owner = relationship("User", back_populates="digital_assets")
    access_rules = relationship("AccessRule", back_populates="digital_asset")

class AccessRule(Base, TimestampMixin):
    __tablename__ = "access_rules"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    digital_asset_id = Column(Integer, ForeignKey("digital_assets.id"))
    beneficiary_address = Column(String)
    access_type = Column(String)  # view, download, manage
    trigger_condition = Column(String)  # date, event, immediate
    trigger_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    smart_contract_id = Column(String, nullable=True)
    
    # Relationships
    owner = relationship("User", back_populates="access_rules")
    digital_asset = relationship("DigitalAsset", back_populates="access_rules")

class ScheduledMessage(Base, TimestampMixin):
    __tablename__ = "scheduled_messages"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    recipient_address = Column(String)
    message_content = Column(Text)
    delivery_date = Column(DateTime)
    is_delivered = Column(Boolean, default=False)
    encryption_key = Column(String)
    blockchain_hash = Column(String)
    
    # Relationships
    owner = relationship("User", back_populates="scheduled_messages") 