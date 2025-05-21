import random
import string
from datetime import datetime, timedelta
from typing import Dict, Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.otp_store: Dict[str, Dict] = {}  # Store OTPs temporarily
        self.otp_expiry = timedelta(minutes=5)  # OTP expires after 5 minutes

    def generate_otp(self) -> str:
        """Generate a 6-digit OTP"""
        return ''.join(random.choices(string.digits, k=6))

    def send_otp_email(self, email: str, otp: str) -> bool:
        """Send OTP via email"""
        try:
            logger.info(f"Attempting to send OTP to {email}")
            logger.info(f"Using SMTP settings - Host: {settings.SMTP_HOST}, Port: {settings.SMTP_PORT}, Username: {settings.SMTP_USERNAME}")
            
            msg = MIMEMultipart()
            msg['From'] = settings.SMTP_USERNAME
            msg['To'] = email
            msg['Subject'] = "Your Digital Legacy Manager OTP"

            body = f"""
            <html>
                <body>
                    <h2>Your OTP for Digital Legacy Manager</h2>
                    <p>Your OTP is: <strong>{otp}</strong></p>
                    <p>This OTP will expire in 5 minutes.</p>
                    <p>If you didn't request this OTP, please ignore this email.</p>
                </body>
            </html>
            """
            msg.attach(MIMEText(body, 'html'))

            logger.info("Connecting to SMTP server...")
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                logger.info("Starting TLS...")
                server.starttls()
                logger.info("Logging in to SMTP server...")
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                logger.info("Sending email...")
                server.send_message(msg)
                logger.info("Email sent successfully!")
            return True
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP Authentication Error: {str(e)}")
            logger.error("Please check your SMTP_USERNAME and SMTP_PASSWORD in .env file")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP Error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email: {str(e)}")
            return False

    def store_otp(self, email: str, otp: str) -> None:
        """Store OTP with expiry time"""
        self.otp_store[email] = {
            'otp': otp,
            'expires_at': datetime.now() + self.otp_expiry
        }
        logger.info(f"OTP stored for {email}")

    def verify_otp(self, email: str, otp: str) -> bool:
        """Verify OTP and check if it's expired"""
        stored_data = self.otp_store.get(email)
        if not stored_data:
            logger.warning(f"No OTP found for {email}")
            return False

        if datetime.now() > stored_data['expires_at']:
            logger.warning(f"OTP expired for {email}")
            del self.otp_store[email]
            return False

        if stored_data['otp'] != otp:
            logger.warning(f"Invalid OTP provided for {email}")
            return False

        # OTP is valid, remove it from store
        del self.otp_store[email]
        logger.info(f"OTP verified successfully for {email}")
        return True

    def send_otp(self, email: str) -> bool:
        """Generate and send OTP"""
        otp = self.generate_otp()
        logger.info(f"Generated OTP for {email}")
        if self.send_otp_email(email, otp):
            self.store_otp(email, otp)
            return True
        return False

# Create a singleton instance
email_service = EmailService() 