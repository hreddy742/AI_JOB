"""auth system hardening

Revision ID: 0002_auth_hardening
Revises: 0001_initial
Create Date: 2026-02-20 18:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002_auth_hardening"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("full_name", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("avatar_url", sa.String(length=500), nullable=True))
    op.add_column("users", sa.Column("auth_provider", sa.String(length=20), nullable=False, server_default="email"))
    op.add_column("users", sa.Column("google_id", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("users", sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("last_login_ip", sa.String(length=45), nullable=True))
    op.add_column("users", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")))

    op.execute(sa.text("UPDATE users SET full_name = split_part(email, '@', 1) WHERE full_name IS NULL"))
    op.alter_column("users", "full_name", nullable=False)

    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=True)

    op.create_index("idx_users_google_id", "users", ["google_id"], unique=True, postgresql_where=sa.text("google_id IS NOT NULL"))

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=50), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_hash"),
    )
    op.create_index("idx_rt_user_id", "refresh_tokens", ["user_id", "revoked_at"], unique=False)
    op.create_index("idx_rt_hash", "refresh_tokens", ["token_hash"], unique=False)
    op.create_index("idx_rt_family", "refresh_tokens", ["family_id"], unique=False)
    op.create_index("idx_rt_expires", "refresh_tokens", ["expires_at"], unique=False)

    op.create_table(
        "email_verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("token_hash", name="uq_ev_token_hash"),
    )
    op.create_index("idx_ev_user_id", "email_verifications", ["user_id", "used_at"], unique=False)
    op.create_index("idx_ev_hash", "email_verifications", ["token_hash"], unique=False)

    op.create_table(
        "password_resets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("token_hash", name="uq_pr_token_hash"),
    )
    op.create_index("idx_pr_user_id", "password_resets", ["user_id", "used_at"], unique=False)
    op.create_index("idx_pr_hash", "password_resets", ["token_hash"], unique=False)

    op.create_table(
        "auth_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_ae_user_id", "auth_events", ["user_id", "created_at"], unique=False)
    op.create_index("idx_ae_event_type", "auth_events", ["event_type", "created_at"], unique=False)
    op.create_index("idx_ae_created_at", "auth_events", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_ae_created_at", table_name="auth_events")
    op.drop_index("idx_ae_event_type", table_name="auth_events")
    op.drop_index("idx_ae_user_id", table_name="auth_events")
    op.drop_table("auth_events")

    op.drop_index("idx_pr_hash", table_name="password_resets")
    op.drop_index("idx_pr_user_id", table_name="password_resets")
    op.drop_table("password_resets")

    op.drop_index("idx_ev_hash", table_name="email_verifications")
    op.drop_index("idx_ev_user_id", table_name="email_verifications")
    op.drop_table("email_verifications")

    op.drop_index("idx_rt_expires", table_name="refresh_tokens")
    op.drop_index("idx_rt_family", table_name="refresh_tokens")
    op.drop_index("idx_rt_hash", table_name="refresh_tokens")
    op.drop_index("idx_rt_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("idx_users_google_id", table_name="users")

    op.drop_column("users", "updated_at")
    op.drop_column("users", "last_login_ip")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_count")
    op.drop_column("users", "is_active")
    op.drop_column("users", "google_id")
    op.drop_column("users", "auth_provider")
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "full_name")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "email_verified")

    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=False)
