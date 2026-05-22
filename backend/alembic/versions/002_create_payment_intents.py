"""create payment_intents table

Revision ID: 002
Revises: 001
Create Date: 2026-05-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_intents",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("merchant_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), server_default="usd", nullable=False),
        sa.Column("status", sa.String(20), server_default="CREATED", nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        sa.Column("failure_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], name="fk_payment_intents_merchant"),
        sa.CheckConstraint("amount > 0", name="ck_payment_intents_amount_positive"),
        sa.CheckConstraint(
            "status IN ('CREATED', 'PROCESSING', 'SUCCEEDED', 'FAILED', 'TIMED_OUT')",
            name="ck_payment_intents_status",
        ),
        sa.UniqueConstraint("merchant_id", "idempotency_key", name="uq_payment_intent_idempotency"),
    )
    op.create_index("ix_payment_intents_merchant_id", "payment_intents", ["merchant_id"])
    op.create_index("ix_payment_intents_status", "payment_intents", ["status"])


def downgrade() -> None:
    op.drop_table("payment_intents")
