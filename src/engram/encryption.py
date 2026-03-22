"""Encryption helpers using Fernet symmetric encryption."""

from cryptography.fernet import Fernet

from engram.config import settings


def get_fernet() -> Fernet:
    if not settings.engram_encryption_key:
        raise ValueError("ENGRAM_ENCRYPTION_KEY not set.")
    return Fernet(settings.engram_encryption_key.encode())


def encrypt(plaintext: str) -> str:
    return get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return get_fernet().decrypt(ciphertext.encode()).decode()


def generate_key() -> str:
    return Fernet.generate_key().decode()
