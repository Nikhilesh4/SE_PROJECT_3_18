"""Resume-extracted identity on profiles: name and social links.

Revision ID: 0007_profile_identity
Revises: 0006_tracker_missions
Create Date: 2026-11-11
"""
from alembic import op

revision = "0007_profile_identity"
down_revision = "0006_tracker_missions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS parsed_name VARCHAR")
    op.execute("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS parsed_socials TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE profiles DROP COLUMN IF EXISTS parsed_socials")
    op.execute("ALTER TABLE profiles DROP COLUMN IF EXISTS parsed_name")
