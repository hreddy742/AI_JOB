"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-02-19 12:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _enable_rls(table: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"CREATE POLICY tenant_isolation ON {table} USING (tenant_id = current_setting('app.tenant_id')::uuid)"
        )
    )


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))

    plan_enum = sa.Enum("free", "pro", "growth", "enterprise", name="plan_enum")
    role_enum = sa.Enum("admin", "user", "coach", name="role_enum")
    job_type_enum = sa.Enum("full_time", "part_time", "contract", "internship", "unknown", name="job_type_enum")
    exp_enum = sa.Enum("entry", "mid", "senior", "lead", "executive", "unknown", name="experience_level_enum")
    app_enum = sa.Enum("draft", "submitted", "interviewing", "rejected", "offer", "withdrawn", name="application_status_enum")
    outreach_enum = sa.Enum("draft", "approved", "sent", "replied", name="outreach_status_enum")
    referral_enum = sa.Enum("pending", "contacted", "converted", "dismissed", name="referral_status_enum")
    chat_enum = sa.Enum("general", "interview_prep", "resume_review", "job_strategy", name="chat_mode_enum")
    severity_enum = sa.Enum("info", "medium", "high", "critical", name="severity_enum")

    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("plan", plan_enum, nullable=False, server_default="free"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", role_enum, nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )

    op.create_table(
        "user_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=True),
        sa.Column("last_name", sa.String(length=100), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("linkedin_url", sa.String(length=500), nullable=True),
        sa.Column("github_url", sa.String(length=500), nullable=True),
        sa.Column("portfolio_url", sa.String(length=500), nullable=True),
        sa.Column("current_location", sa.String(length=255), nullable=True),
        sa.Column("work_authorization", sa.String(length=100), nullable=True),
        sa.Column("target_roles", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("target_locations", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("target_salary_min", sa.Numeric(12, 2), nullable=True),
        sa.Column("target_salary_max", sa.Numeric(12, 2), nullable=True),
        sa.Column("years_experience", sa.Integer(), nullable=True),
        sa.Column("summary_bio", sa.Text(), nullable=True),
        sa.Column("headline", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("fingerprint", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("location_city", sa.String(length=255), nullable=True),
        sa.Column("location_state", sa.String(length=100), nullable=True),
        sa.Column("location_country", sa.String(length=100), nullable=True),
        sa.Column("remote", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sponsorship_score", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("salary_min", sa.Numeric(12, 2), nullable=True),
        sa.Column("salary_max", sa.Numeric(12, 2), nullable=True),
        sa.Column("salary_currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("job_type", job_type_enum, nullable=False, server_default="unknown"),
        sa.Column("experience_level", exp_enum, nullable=False, server_default="unknown"),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("typesense_synced", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.UniqueConstraint("source", "source_id", name="uq_jobs_source_source_id"),
    )
    op.create_index("ix_jobs_tenant_posted_at", "jobs", ["tenant_id", "posted_at"], unique=False)
    op.create_index("ix_jobs_company_title", "jobs", ["company", "title"], unique=False)
    op.create_index("ix_jobs_fingerprint", "jobs", ["fingerprint"], unique=False)
    op.create_index("ix_jobs_tags_gin", "jobs", ["tags"], unique=False, postgresql_using="gin")

    op.create_table(
        "resumes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("parsed_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("embedding_id", sa.String(length=255), nullable=True),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "tailored_resumes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_resume_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tailored_text", sa.Text(), nullable=False),
        sa.Column("diff_log", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reviewer_score", sa.Float(), nullable=True),
        sa.Column("supervisor_approved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("violations", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    op.create_table(
        "applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tailored_resume_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tailored_resumes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", app_enum, nullable=False, server_default="draft"),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("automation_log", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("follow_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_applications_user_status", "applications", ["user_id", "status"], unique=False)
    op.create_index("ix_applications_job_user", "applications", ["job_id", "user_id"], unique=False)

    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("linkedin_url", sa.String(length=500), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "outreach_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("draft_text", sa.Text(), nullable=False),
        sa.Column("compliance_score", sa.Float(), nullable=True),
        sa.Column("status", outreach_enum, nullable=False, server_default="draft"),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reply_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    op.create_table(
        "referral_suggestions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("contact_name", sa.String(length=255), nullable=True),
        sa.Column("contact_title", sa.String(length=255), nullable=True),
        sa.Column("contact_source", sa.String(length=100), nullable=True),
        sa.Column("contact_url", sa.String(length=500), nullable=True),
        sa.Column("inferred_email", sa.String(length=255), nullable=True),
        sa.Column("email_pattern", sa.String(length=100), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("discovery_method", sa.String(length=100), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", referral_enum, nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_referral_suggestions_user_job", "referral_suggestions", ["user_id", "job_id"], unique=False)
    op.create_index("ix_referral_suggestions_company_status", "referral_suggestions", ["company", "status"], unique=False)

    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("mode", chat_enum, nullable=False, server_default="general"),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resume_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("messages", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_chat_sessions_user_created", "chat_sessions", ["user_id", "created_at"], unique=False)

    op.create_table(
        "supervisor_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("severity", severity_enum, nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index(
        "ix_supervisor_logs_tenant_severity_created",
        "supervisor_logs",
        ["tenant_id", "severity", "created_at"],
        unique=False,
    )

    op.execute(sa.text("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("CREATE POLICY tenant_isolation ON tenants USING (id = current_setting('app.tenant_id')::uuid)"))

    for table in [
        "users",
        "user_profiles",
        "jobs",
        "resumes",
        "tailored_resumes",
        "applications",
        "contacts",
        "outreach_messages",
        "referral_suggestions",
        "chat_sessions",
        "supervisor_logs",
    ]:
        _enable_rls(table)


def downgrade() -> None:
    for table in [
        "supervisor_logs",
        "chat_sessions",
        "referral_suggestions",
        "outreach_messages",
        "contacts",
        "applications",
        "tailored_resumes",
        "resumes",
        "jobs",
        "user_profiles",
        "users",
        "tenants",
    ]:
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))

    op.drop_index("ix_supervisor_logs_tenant_severity_created", table_name="supervisor_logs")
    op.drop_table("supervisor_logs")
    op.drop_index("ix_chat_sessions_user_created", table_name="chat_sessions")
    op.drop_table("chat_sessions")
    op.drop_index("ix_referral_suggestions_company_status", table_name="referral_suggestions")
    op.drop_index("ix_referral_suggestions_user_job", table_name="referral_suggestions")
    op.drop_table("referral_suggestions")
    op.drop_table("outreach_messages")
    op.drop_table("contacts")
    op.drop_index("ix_applications_job_user", table_name="applications")
    op.drop_index("ix_applications_user_status", table_name="applications")
    op.drop_table("applications")
    op.drop_table("tailored_resumes")
    op.drop_table("resumes")
    op.drop_index("ix_jobs_tags_gin", table_name="jobs")
    op.drop_index("ix_jobs_fingerprint", table_name="jobs")
    op.drop_index("ix_jobs_company_title", table_name="jobs")
    op.drop_index("ix_jobs_tenant_posted_at", table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("user_profiles")
    op.drop_table("users")
    op.drop_table("tenants")

    for enum_name in [
        "severity_enum",
        "chat_mode_enum",
        "referral_status_enum",
        "outreach_status_enum",
        "application_status_enum",
        "experience_level_enum",
        "job_type_enum",
        "role_enum",
        "plan_enum",
    ]:
        op.execute(sa.text(f"DROP TYPE IF EXISTS {enum_name}"))
