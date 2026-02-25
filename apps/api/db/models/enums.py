"""Database enum types shared across models."""

from enum import Enum


class PlanEnum(str, Enum):
    """Tenant billing plans."""

    free = "free"
    pro = "pro"
    growth = "growth"
    enterprise = "enterprise"


class RoleEnum(str, Enum):
    """Application roles."""

    admin = "admin"
    user = "user"
    coach = "coach"


class JobTypeEnum(str, Enum):
    """Supported job types."""

    full_time = "full_time"
    part_time = "part_time"
    contract = "contract"
    internship = "internship"
    unknown = "unknown"


class ExperienceLevelEnum(str, Enum):
    """Job seniority levels."""

    entry = "entry"
    mid = "mid"
    senior = "senior"
    lead = "lead"
    executive = "executive"
    unknown = "unknown"


class ApplicationStatusEnum(str, Enum):
    """Application pipeline statuses."""

    draft = "draft"
    submitted = "submitted"
    interviewing = "interviewing"
    rejected = "rejected"
    offer = "offer"
    withdrawn = "withdrawn"


class OutreachStatusEnum(str, Enum):
    """Outreach status lifecycle."""

    draft = "draft"
    approved = "approved"
    sent = "sent"
    replied = "replied"


class ReferralStatusEnum(str, Enum):
    """Referral suggestion statuses."""

    pending = "pending"
    contacted = "contacted"
    converted = "converted"
    dismissed = "dismissed"


class ChatModeEnum(str, Enum):
    """Copilot chat modes."""

    general = "general"
    interview_prep = "interview_prep"
    resume_review = "resume_review"
    job_strategy = "job_strategy"


class SeverityEnum(str, Enum):
    """Supervisor severity levels."""

    info = "info"
    medium = "medium"
    high = "high"
    critical = "critical"
