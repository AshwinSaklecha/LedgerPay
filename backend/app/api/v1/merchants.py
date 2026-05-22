import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_current_merchant
from app.core.database import get_conn
from app.models.merchant import Merchant
from app.schemas.merchant import (
    MerchantRegisterRequest,
    MerchantRegisterResponse,
    MerchantResponse,
)
from app.services.merchant_service import DuplicateEmailError, register_merchant

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/merchants", tags=["Merchants"])


@router.post("", response_model=MerchantRegisterResponse, status_code=status.HTTP_201_CREATED)
def create_merchant(body: MerchantRegisterRequest):
    """
    Register a new merchant. Returns the API key **once** — store it securely.
    """
    webhook_url = str(body.webhook_url) if body.webhook_url else None

    with get_conn() as conn:
        try:
            merchant, plaintext_key = register_merchant(
                conn, body.name, body.email, webhook_url
            )
        except DuplicateEmailError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A merchant with this email already exists",
            )

    return MerchantRegisterResponse(
        id=merchant.id,
        name=merchant.name,
        email=merchant.email,
        webhook_url=merchant.webhook_url,
        api_key=plaintext_key,
        created_at=merchant.created_at,
    )


@router.get("/me", response_model=MerchantResponse)
def get_me(current: Merchant = Depends(get_current_merchant)):
    """Return the authenticated merchant's profile."""
    return MerchantResponse(
        id=current.id,
        name=current.name,
        email=current.email,
        webhook_url=current.webhook_url,
        is_active=current.is_active,
        created_at=current.created_at,
    )
