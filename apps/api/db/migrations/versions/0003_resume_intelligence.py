"""resume intelligence schema

Revision ID: 0003_resume_intelligence
Revises: 0002_auth_hardening
Create Date: 2026-02-20 20:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0003_resume_intelligence"
down_revision = "0002_auth_hardening"
branch_labels = None
depends_on = None


RESUME_TABLES = [
    "resumes",
    "resume_parsed_data",
    "tailored_resumes",
    "cover_letters",
    "resume_reviews",
    "resume_versions",
]
TENANT_TABLES = [
    "resumes",
    "resume_parsed_data",
    "tailored_resumes",
    "cover_letters",
    "resume_reviews",
]


def _set_user_policy(table: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
    op.execute(sa.text(f"DROP POLICY IF EXISTS {table}_isolation ON {table}"))
    op.execute(
        sa.text(
            f"CREATE POLICY {table}_isolation ON {table} "
            "USING (user_id = current_setting('app.user_id', true)::uuid)"
        )
    )


def upgrade() -> None:
    op.add_column("resumes", sa.Column("label", sa.String(length=100), nullable=False, server_default="My Resume"))
    op.add_column("resumes", sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("resumes", sa.Column("file_name", sa.String(length=255), nullable=True))
    op.add_column("resumes", sa.Column("file_size_bytes", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("resumes", sa.Column("file_type", sa.String(length=20), nullable=True))
    op.add_column("resumes", sa.Column("raw_text", sa.Text(), nullable=True))
    op.add_column("resumes", sa.Column("parse_status", sa.String(length=20), nullable=False, server_default="pending"))
    op.add_column("resumes", sa.Column("parse_error", sa.Text(), nullable=True))
    op.add_column("resumes", sa.Column("parse_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("resumes", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")))

    op.execute(sa.text("UPDATE resumes SET file_name = COALESCE(file_path, 'resume.txt') WHERE file_name IS NULL"))
    op.execute(sa.text("UPDATE resumes SET file_type = 'txt' WHERE file_type IS NULL"))
    op.execute(sa.text("UPDATE resumes SET raw_text = original_text WHERE raw_text IS NULL"))
    op.alter_column("resumes", "file_name", nullable=False)
    op.alter_column("resumes", "file_type", nullable=False)

    op.create_index("ix_resumes_user_id", "resumes", ["user_id"], unique=False)
    op.create_index(
        "ix_resumes_user_primary",
        "resumes",
        ["user_id", "is_primary"],
        unique=False,
        postgresql_where=sa.text("is_primary = true"),
    )

    op.create_table(
        "resume_parsed_data",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("resume_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_name", sa.String(length=200), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=50), nullable=True),
        sa.Column("contact_location", sa.String(length=200), nullable=True),
        sa.Column("contact_linkedin", sa.String(length=500), nullable=True),
        sa.Column("contact_github", sa.String(length=500), nullable=True),
        sa.Column("contact_website", sa.String(length=500), nullable=True),
        sa.Column("contact_other", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("work_experience", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("education", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("skills_all", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("skills_technical", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("skills_soft", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("skills_languages", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("skills_certifications", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("projects", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("awards", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("publications", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("volunteer", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("additional", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("total_years_experience", sa.Numeric(4, 1), nullable=True),
        sa.Column("seniority_level", sa.String(length=20), nullable=True),
        sa.Column("primary_domain", sa.String(length=100), nullable=True),
        sa.Column("primary_job_titles", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("industry_keywords", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parser_model", sa.String(length=100), nullable=True),
    )
    op.create_index("ix_resume_parsed_data_resume_id", "resume_parsed_data", ["resume_id"], unique=False)
    op.create_index("ix_resume_parsed_data_user_id", "resume_parsed_data", ["user_id"], unique=False)

    op.add_column("tailored_resumes", sa.Column("job_title_target", sa.String(length=255), nullable=True))
    op.add_column("tailored_resumes", sa.Column("company_target", sa.String(length=255), nullable=True))
    op.add_column("tailored_resumes", sa.Column("tailored_parsed", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("tailored_resumes", sa.Column("ats_score", sa.Numeric(5, 2), nullable=True))
    op.add_column("tailored_resumes", sa.Column("quality_score", sa.Numeric(5, 2), nullable=True))
    op.add_column("tailored_resumes", sa.Column("violation_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("tailored_resumes", sa.Column("review_report", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("tailored_resumes", sa.Column("supervisor_decision", sa.String(length=20), nullable=True))
    op.add_column("tailored_resumes", sa.Column("generation_model", sa.String(length=100), nullable=True))
    op.add_column("tailored_resumes", sa.Column("status", sa.String(length=20), nullable=False, server_default="generating"))
    op.add_column("tailored_resumes", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")))
    op.create_index("ix_tailored_resumes_user_id", "tailored_resumes", ["user_id"], unique=False)
    op.create_index("ix_tailored_resumes_source_resume_id", "tailored_resumes", ["source_resume_id"], unique=False)
    op.create_index("ix_tailored_resumes_job_id", "tailored_resumes", ["job_id"], unique=False)

    op.create_table(
        "cover_letters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_resume_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tailored_resume_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tailored_resumes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_title_target", sa.String(length=255), nullable=True),
        sa.Column("company_target", sa.String(length=255), nullable=True),
        sa.Column("hiring_manager_name", sa.String(length=200), nullable=True),
        sa.Column("tone", sa.String(length=30), nullable=False, server_default="professional"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("generation_model", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_cover_letters_user_id", "cover_letters", ["user_id"], unique=False)

    op.create_table(
        "resume_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resume_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("review_type", sa.String(length=30), nullable=False),
        sa.Column("overall_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("ats_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("impact_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("clarity_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("completeness_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("format_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("full_report", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("key_issues", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("quick_wins", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("model_used", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_resume_reviews_user_id", "resume_reviews", ["user_id"], unique=False)
    op.create_index("ix_resume_reviews_resume_id", "resume_reviews", ["resume_id"], unique=False)

    op.create_table(
        "resume_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resume_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("content_parsed", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("change_summary", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("resume_id", "version_number", name="uq_resume_versions_resume_version"),
    )
    op.create_index("ix_resume_versions_resume_version", "resume_versions", ["resume_id", "version_number"], unique=False)

    for table in RESUME_TABLES:
        _set_user_policy(table)


def downgrade() -> None:
    for table in reversed(RESUME_TABLES):
        op.execute(sa.text(f"DROP POLICY IF EXISTS {table}_isolation ON {table}"))
    for table in TENANT_TABLES:
        op.execute(sa.text(f"CREATE POLICY tenant_isolation ON {table} USING (tenant_id = current_setting('app.tenant_id')::uuid)"))

    op.drop_index("ix_resume_versions_resume_version", table_name="resume_versions")
    op.drop_table("resume_versions")

    op.drop_index("ix_resume_reviews_resume_id", table_name="resume_reviews")
    op.drop_index("ix_resume_reviews_user_id", table_name="resume_reviews")
    op.drop_table("resume_reviews")

    op.drop_index("ix_cover_letters_user_id", table_name="cover_letters")
    op.drop_table("cover_letters")

    op.drop_index("ix_tailored_resumes_job_id", table_name="tailored_resumes")
    op.drop_index("ix_tailored_resumes_source_resume_id", table_name="tailored_resumes")
    op.drop_index("ix_tailored_resumes_user_id", table_name="tailored_resumes")
    op.drop_column("tailored_resumes", "updated_at")
    op.drop_column("tailored_resumes", "status")
    op.drop_column("tailored_resumes", "generation_model")
    op.drop_column("tailored_resumes", "supervisor_decision")
    op.drop_column("tailored_resumes", "review_report")
    op.drop_column("tailored_resumes", "violation_count")
    op.drop_column("tailored_resumes", "quality_score")
    op.drop_column("tailored_resumes", "ats_score")
    op.drop_column("tailored_resumes", "tailored_parsed")
    op.drop_column("tailored_resumes", "company_target")
    op.drop_column("tailored_resumes", "job_title_target")

    op.drop_index("ix_resume_parsed_data_user_id", table_name="resume_parsed_data")
    op.drop_index("ix_resume_parsed_data_resume_id", table_name="resume_parsed_data")
    op.drop_table("resume_parsed_data")

    op.drop_index("ix_resumes_user_primary", table_name="resumes")
    op.drop_index("ix_resumes_user_id", table_name="resumes")
    op.drop_column("resumes", "updated_at")
    op.drop_column("resumes", "parse_version")
    op.drop_column("resumes", "parse_error")
    op.drop_column("resumes", "parse_status")
    op.drop_column("resumes", "raw_text")
    op.drop_column("resumes", "file_type")
    op.drop_column("resumes", "file_size_bytes")
    op.drop_column("resumes", "file_name")
    op.drop_column("resumes", "is_primary")
    op.drop_column("resumes", "label")
