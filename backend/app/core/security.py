"""API key generation and hashing."""
import hashlib
import secrets


API_KEY_PREFIX = "lp_"


def generate_api_key() -> str:
    """Generate a secure plaintext API key. Shown to merchant exactly once."""
    return API_KEY_PREFIX + secrets.token_hex(32)


def hash_api_key(plaintext_key: str) -> str:
    """SHA-256 hash of the key. This is what we store in the database."""
    return hashlib.sha256(plaintext_key.encode()).hexdigest()


def verify_api_key(plaintext_key: str, stored_hash: str) -> bool:
    return hashlib.compare_digest(hash_api_key(plaintext_key), stored_hash)
