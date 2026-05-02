"""bundled assets and token image kind

Revision ID: 20260502_0013
Revises: 20260427_0012
Create Date: 2026-05-02
"""

from __future__ import annotations

from alembic import op


revision = "20260502_0013"
down_revision = "20260427_0012"
branch_labels = None
depends_on = None


ASSET_KIND_CHECK_WITH_TOKEN = (
    "kind in ('map_image', 'handout_image', 'npc_portrait', 'item_image', "
    "'scene_image', 'token_image', 'audio', 'markdown', 'pdf', 'other')"
)
ASSET_KIND_CHECK_WITHOUT_TOKEN = (
    "kind in ('map_image', 'handout_image', 'npc_portrait', 'item_image', "
    "'scene_image', 'audio', 'markdown', 'pdf', 'other')"
)
ASSET_VISIBILITY_CHECK = "visibility in ('private', 'public_displayable')"


def _rebuild_assets(kind_check: str) -> None:
    with op.batch_alter_table("assets", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_assets_kind", type_="check")
        batch_op.drop_constraint("ck_assets_visibility", type_="check")
        batch_op.create_check_constraint("ck_assets_kind", kind_check)
        batch_op.create_check_constraint("ck_assets_visibility", ASSET_VISIBILITY_CHECK)


def upgrade() -> None:
    _rebuild_assets(ASSET_KIND_CHECK_WITH_TOKEN)


def downgrade() -> None:
    op.execute("UPDATE assets SET kind = 'npc_portrait' WHERE kind = 'token_image'")
    _rebuild_assets(ASSET_KIND_CHECK_WITHOUT_TOKEN)
