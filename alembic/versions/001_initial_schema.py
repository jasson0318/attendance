"""Initial schema from SQLAlchemy models (SQLite + PostgreSQL).

Revision ID: 001_initial
Revises:
Create Date: 2026-03-23
"""
from __future__ import annotations

import sys
from pathlib import Path

from alembic import op

# revision identifiers
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def upgrade() -> None:
    """空庫 → 完整 schema（依 models metadata）。"""
    from backend.app.database import Base
    from backend.app import models  # noqa: F401
    from backend.app.services import preview_store  # noqa: F401

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from backend.app.database import Base
    from backend.app import models  # noqa: F401
    from backend.app.services import preview_store  # noqa: F401

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
