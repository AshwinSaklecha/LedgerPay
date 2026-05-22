"""create ledger_entries table

Revision ID: 003
Revises: 002
Create Date: 2026-05-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("payment_intent_id", sa.UUID(), nullable=False),
        sa.Column("merchant_id", sa.UUID(), nullable=False),
        sa.Column(
            "entry_type",
            sa.String(6),
            nullable=False,
            comment="DEBIT or CREDIT",
        ),
        sa.Column(
            "account_type",
            sa.String(10),
            nullable=False,
            comment="CUSTOMER or MERCHANT",
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["payment_intent_id"], ["payment_intents.id"],
            name="fk_ledger_payment_intent",
        ),
        sa.ForeignKeyConstraint(
            ["merchant_id"], ["merchants.id"],
            name="fk_ledger_merchant",
        ),
        sa.CheckConstraint("amount > 0", name="ck_ledger_amount_positive"),
        sa.CheckConstraint("entry_type IN ('DEBIT', 'CREDIT')", name="ck_ledger_entry_type"),
        sa.CheckConstraint("account_type IN ('CUSTOMER', 'MERCHANT')", name="ck_ledger_account_type"),
    )
    op.create_index("ix_ledger_payment_intent_id", "ledger_entries", ["payment_intent_id"])
    op.create_index("ix_ledger_merchant_id", "ledger_entries", ["merchant_id"])


def downgrade() -> None:
    op.drop_table("ledger_entries")
