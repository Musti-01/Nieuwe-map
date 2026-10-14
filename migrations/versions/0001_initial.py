"""Initial SaaS schema. Frozen migration independent of future model changes."""
from alembic import op
import sqlalchemy as sa
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("users", sa.Column("id", sa.Integer, primary_key=True), sa.Column("email", sa.String(254), nullable=False, unique=True), sa.Column("name", sa.String(120), nullable=False), sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("platform_admin", sa.Boolean, nullable=False))
    op.create_table("organizations", sa.Column("id", sa.Integer, primary_key=True), sa.Column("name", sa.String(120), nullable=False), sa.Column("chain", sa.String(120), nullable=False), sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False), sa.Column("primary_color", sa.String(7), nullable=False), sa.Column("secondary_color", sa.String(7), nullable=False))
    op.create_table("branches", sa.Column("id", sa.Integer, primary_key=True), sa.Column("organization_id", sa.Integer, sa.ForeignKey("organizations.id"), nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.Column("plan", sa.String(30), nullable=False))
    op.create_index("ix_branches_organization_id", "branches", ["organization_id"])
    op.create_table("memberships", sa.Column("branch_id", sa.Integer, sa.ForeignKey("branches.id"), primary_key=True), sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True), sa.Column("role", sa.String(20), nullable=False), sa.CheckConstraint("role IN ('admin', 'employee', 'revoked')", name="valid_role"))
    op.create_table("work_entries", sa.Column("id", sa.Integer, primary_key=True), sa.Column("branch_id", sa.Integer, nullable=False), sa.Column("user_id", sa.Integer, nullable=False), sa.Column("started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("ended_at", sa.DateTime(timezone=True)), sa.ForeignKeyConstraint(["branch_id", "user_id"], ["memberships.branch_id", "memberships.user_id"]), sa.CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="valid_interval"))
    op.create_index("ix_work_entries_branch_id", "work_entries", ["branch_id"])
    op.create_index("ix_work_entries_user_id", "work_entries", ["user_id"])
    op.create_index("one_active_entry_per_user", "work_entries", ["user_id"], unique=True, postgresql_where=sa.text("ended_at IS NULL"))
    op.create_table("auth_sessions", sa.Column("token_hash", sa.String(64), primary_key=True), sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_table("login_limits", sa.Column("key", sa.String(64), primary_key=True), sa.Column("failures", sa.Integer, nullable=False), sa.Column("window_start", sa.DateTime(timezone=True), nullable=False))
    op.create_table("audit_events", sa.Column("id", sa.Integer, primary_key=True), sa.Column("actor_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False), sa.Column("branch_id", sa.Integer, sa.ForeignKey("branches.id")), sa.Column("action", sa.String(80), nullable=False), sa.Column("detail", sa.String(500), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))

def downgrade():
    for table in ["audit_events", "login_limits", "auth_sessions", "work_entries", "memberships", "branches", "organizations", "users"]:
        op.drop_table(table)
