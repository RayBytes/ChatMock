from __future__ import annotations

import os
import secrets

from flask import request


def _get_or_generate_admin_key() -> str:
    """Get admin key from environment or generate one if not provided"""
    admin_key = _get_admin_key()
    if not admin_key:
        # Generate a secure random key
        admin_key = secrets.token_urlsafe(32)
        os.environ["CHATMOCK_ADMIN_KEY"] = admin_key
        print(f"No CHATMOCK_ADMIN_KEY environment variable set!")
        print(f"Generated and set CHATMOCK_ADMIN_KEY={admin_key}\n")
    else:
        print(f"CHATMOCK_ADMIN_KEY={admin_key} already set\n")
    return admin_key


def _get_admin_key() -> str:
    """Get admin key from environment or generate one if not provided"""
    return os.getenv("CHATMOCK_ADMIN_KEY")


def _validate_admin_key() -> bool:
    """Validate admin key from request headers or query params"""
    admin_key = _get_admin_key()
    
    # Check Authorization header first
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        provided_key = auth_header[7:]  # Remove "Bearer " prefix
        if provided_key == admin_key:
            return True
    
    # Check X-Admin-Key header
    if request.headers.get("X-Admin-Key") == admin_key:
        return True
    
    # Check query parameter
    if request.args.get("admin_key") == admin_key:
        return True
    
    return False