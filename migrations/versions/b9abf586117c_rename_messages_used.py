from alembic import op

revision = "b9abf586117c"
down_revision = "d7b8aa20d79d"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "subscriptions",
        "messages_used",
        new_column_name="message_used"
    )


def downgrade():
    op.alter_column(
        "subscriptions",
        "message_used",
        new_column_name="messages_used"
    )