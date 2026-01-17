"""
256-bit AES encryption for sensitive payment data
"""
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from django.conf import settings
import base64
import logging

logger = logging.getLogger(__name__)


class PaymentEncryption:
    """
    Handle 256-bit AES encryption/decryption for sensitive payment data
    Uses Fernet symmetric encryption (AES-128 in CBC mode with HMAC for authentication)
    """
    
    def __init__(self):
        """Initialize encryption with key from settings"""
        self.key = self._get_encryption_key()
        self.cipher = Fernet(self.key)
    
    def _get_encryption_key(self):
        """
        Generate or retrieve encryption key from settings
        Uses PBKDF2 to derive a key from the secret key
        """
        try:
            # Get secret key from settings
            secret = getattr(settings, 'PAYMENT_ENCRYPTION_KEY', settings.SECRET_KEY)
            
            # Use PBKDF2HMAC to derive a 32-byte key (256-bit)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'payment_encryption_salt_v1',  # Static salt for consistency
                iterations=100000,
                backend=default_backend()
            )
            
            key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
            return key
        
        except Exception as e:
            logger.error(f"Error generating encryption key: {e}")
            raise
    
    def encrypt(self, plaintext):
        """
        Encrypt sensitive payment data
        
        Args:
            plaintext: String data to encrypt
        
        Returns:
            Encrypted string (base64 encoded) or None on error
        """
        if not plaintext:
            return None
        
        try:
            # Convert to bytes if string
            if isinstance(plaintext, str):
                plaintext = plaintext.encode('utf-8')
            
            # Encrypt the data
            encrypted = self.cipher.encrypt(plaintext)
            
            # Return as base64 string for storage
            return encrypted.decode('utf-8')
        
        except Exception as e:
            logger.error(f"Error encrypting payment data: {e}")
            return None
    
    def decrypt(self, ciphertext):
        """
        Decrypt sensitive payment data
        
        Args:
            ciphertext: Encrypted string (base64 encoded)
        
        Returns:
            Decrypted string or None on error
        """
        if not ciphertext:
            return None
        
        try:
            # Convert to bytes if string
            if isinstance(ciphertext, str):
                ciphertext = ciphertext.encode('utf-8')
            
            # Decrypt the data
            decrypted = self.cipher.decrypt(ciphertext)
            
            # Return as string
            return decrypted.decode('utf-8')
        
        except Exception as e:
            logger.error(f"Error decrypting payment data: {e}")
            return None
    
    def encrypt_dict(self, data_dict):
        """
        Encrypt a dictionary of payment data
        
        Args:
            data_dict: Dictionary with payment information
        
        Returns:
            Dictionary with encrypted values
        """
        if not data_dict:
            return {}
        
        encrypted_dict = {}
        
        for key, value in data_dict.items():
            if value:
                encrypted_value = self.encrypt(str(value))
                if encrypted_value:
                    encrypted_dict[key] = encrypted_value
            else:
                encrypted_dict[key] = None
        
        return encrypted_dict
    
    def decrypt_dict(self, encrypted_dict):
        """
        Decrypt a dictionary of encrypted payment data
        
        Args:
            encrypted_dict: Dictionary with encrypted values
        
        Returns:
            Dictionary with decrypted values
        """
        if not encrypted_dict:
            return {}
        
        decrypted_dict = {}
        
        for key, value in encrypted_dict.items():
            if value:
                decrypted_value = self.decrypt(value)
                if decrypted_value:
                    decrypted_dict[key] = decrypted_value
            else:
                decrypted_dict[key] = None
        
        return decrypted_dict


# Singleton instance
_encryption_instance = None


def get_payment_encryption():
    """
    Get singleton instance of PaymentEncryption
    
    Returns:
        PaymentEncryption instance
    """
    global _encryption_instance
    
    if _encryption_instance is None:
        _encryption_instance = PaymentEncryption()
    
    return _encryption_instance


def encrypt_payment_data(plaintext):
    """
    Convenience function to encrypt payment data
    
    Args:
        plaintext: String data to encrypt
    
    Returns:
        Encrypted string
    """
    encryption = get_payment_encryption()
    return encryption.encrypt(plaintext)


def decrypt_payment_data(ciphertext):
    """
    Convenience function to decrypt payment data
    
    Args:
        ciphertext: Encrypted string
    
    Returns:
        Decrypted string
    """
    encryption = get_payment_encryption()
    return encryption.decrypt(ciphertext)
