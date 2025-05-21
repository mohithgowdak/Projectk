from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
import base64
import os
import logging

logger = logging.getLogger(__name__)

class EncryptionService:
    def __init__(self):
        self.salt = os.urandom(16)
        self._ensure_encryption_key()
    
    def _ensure_encryption_key(self):
        """Ensure encryption key exists or create a new one."""
        key_path = "encryption_key.key"
        if os.path.exists(key_path):
            with open(key_path, "rb") as key_file:
                self.key = key_file.read()
        else:
            self.key = Fernet.generate_key()
            with open(key_path, "wb") as key_file:
                key_file.write(self.key)
    
    def generate_key(self) -> bytes:
        """Generate a new encryption key."""
        return Fernet.generate_key()
    
    def derive_key(self, password: str) -> bytes:
        """Derive an encryption key from a password."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def encrypt_data(self, data: bytes, key: bytes) -> bytes:
        """Encrypt data using the provided key."""
        f = Fernet(key)
        return f.encrypt(data)
    
    def decrypt_data(self, encrypted_data: bytes, key: bytes) -> bytes:
        """Decrypt data using the provided key."""
        f = Fernet(key)
        return f.decrypt(encrypted_data)
    
    def encrypt_file(self, file_path: str) -> tuple[str, bytes]:
        """Encrypt a file and return the path to the encrypted file and the encryption key."""
        try:
            # Generate a unique key for this file
            file_key = self.generate_key()
            f = Fernet(file_key)
            
            # Read the file in chunks to handle large files
            chunk_size = 64 * 1024  # 64KB chunks
            encrypted_path = f"{file_path}.encrypted"
            
            with open(file_path, 'rb') as infile, open(encrypted_path, 'wb') as outfile:
                while True:
                    chunk = infile.read(chunk_size)
                    if not chunk:
                        break
                    encrypted_chunk = f.encrypt(chunk)
                    outfile.write(encrypted_chunk)
            
            logger.info(f"Successfully encrypted file: {file_path}")
            return encrypted_path, file_key
            
        except Exception as e:
            logger.error(f"Error encrypting file {file_path}: {str(e)}")
            raise Exception(f"Failed to encrypt file: {str(e)}")
    
    def decrypt_file(self, encrypted_file_path: str, key: bytes) -> str:
        """Decrypt a file and return the path to the decrypted file."""
        try:
            f = Fernet(key)
            decrypted_path = encrypted_file_path.replace('.encrypted', '')
            
            # Read and decrypt in chunks
            chunk_size = 64 * 1024  # 64KB chunks
            
            with open(encrypted_file_path, 'rb') as infile, open(decrypted_path, 'wb') as outfile:
                while True:
                    chunk = infile.read(chunk_size)
                    if not chunk:
                        break
                    decrypted_chunk = f.decrypt(chunk)
                    outfile.write(decrypted_chunk)
            
            logger.info(f"Successfully decrypted file: {encrypted_file_path}")
            return decrypted_path
            
        except Exception as e:
            logger.error(f"Error decrypting file {encrypted_file_path}: {str(e)}")
            raise Exception(f"Failed to decrypt file: {str(e)}")

encryption_service = EncryptionService() 