from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class Merchant:
    id: UUID
    name: str
    email: str
    hashed_api_key: str
    webhook_url: str | None
    is_active: bool
    created_at: datetime
