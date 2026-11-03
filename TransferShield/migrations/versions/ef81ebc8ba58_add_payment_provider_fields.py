"""add payment provider fields

Revision ID: ef81ebc8ba58
Revises: 97e343866152
Create Date: 2026-10-16 12:49:18.542902

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ef81ebc8ba58'
down_revision: Union[str, None] = '97e343866152'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'payments',
        sa.Column('customer_email', sa.String(length=254), nullable=True),
    )
    op.add_column(
        'payments',
        sa.Column('provider_reference', sa.String(length=100), nullable=True),
    )

    with op.batch_alter_table('payments') as batch_op:
        batch_op.create_unique_constraint(
            'uq_payments_provider_reference',
            ['provider_reference'],
        )


def downgrade() -> None:
    with op.batch_alter_table('payments') as batch_op:
        batch_op.drop_constraint(
            'uq_payments_provider_reference',
            type_='unique',
        )

    op.drop_column('payments', 'provider_reference')
    op.drop_column('payments', 'customer_email')