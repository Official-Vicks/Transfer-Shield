"""add unique merchant payment reference

Revision ID: 97e343866152
Revises: b9ae2c466832
Create Date: 2026-10-06 18:46:16.333746

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '97e343866152'
down_revision: Union[str, None] = 'b9ae2c466832'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("payments") as batch_op:
        batch_op.create_unique_constraint(
            "uq_payment_merchant_reference",
            ["merchant_id", "reference"],
        )


def downgrade() -> None:
    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_constraint(
            "uq_payment_merchant_reference",
            type_="unique",
        )
