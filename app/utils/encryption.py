"""Encryption utilities for secure API key storage."""
from cryptography.fernet import Fernet
from app.config import settings
import base64
import hashlib


def _get_fernet() -> Fernet:
    """Get Fernet cipher from configured key."""
    # Ensure key is properly formatted for Fernet (32 bytes, base64 encoded)
    key = settings.encryption_key.encode()
    # Hash it to get consistent 32 bytes, then base64 encode
    key_bytes = hashlib.sha256(key).digest()
    key_b64 = base64.urlsafe_b64encode(key_bytes)
    return Fernet(key_b64)


def encrypt_api_key(api_key: str) -> str:
    """
    Encrypt an API key for secure storage.

    Args:
        api_key: The plain text API key

    Returns:
        Encrypted API key as a base64 string
    """
    if not api_key:
        return ""

    fernet = _get_fernet()
    encrypted = fernet.encrypt(api_key.encode())
    return encrypted.decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """
    Decrypt an API key for use.

    Args:
        encrypted_key: The encrypted API key

    Returns:
        Decrypted plain text API key
    """
    if not encrypted_key:
        return ""

    fernet = _get_fernet()
    decrypted = fernet.decrypt(encrypted_key.encode())
    return decrypted.decode()


def mask_api_key(api_key: str, visible_chars: int = 4) -> str:
    """
    Mask an API key for display purposes.

    Args:
        api_key: The API key to mask
        visible_chars: Number of characters to show at the end

    Returns:
        Masked API key (e.g., "****abc123")
    """
    if not api_key or len(api_key) <= visible_chars:
        return "****"

    return f"{'*' * (len(api_key) - visible_chars)}{api_key[-visible_chars:]}"
