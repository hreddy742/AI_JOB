"""Model exports for metadata registration."""

from db.models.application import Application
from db.models.auth_event import AuthEvent
from db.models.chat_session import ChatSession
from db.models.contact import Contact
from db.models.cover_letter import CoverLetter
from db.models.email_verification import EmailVerification
from db.models.job import Job
from db.models.outreach import OutreachMessage
from db.models.password_reset import PasswordReset
from db.models.referral import ReferralSuggestion
from db.models.refresh_token import RefreshToken
from db.models.resume_parsed_data import ResumeParsedData
from db.models.resume_review import ResumeReview
from db.models.resume_version import ResumeVersion
from db.models.resume import Resume, TailoredResume
from db.models.supervisor_log import SupervisorLog
from db.models.tenant import Tenant
from db.models.user import User
from db.models.user_profile import UserProfile

__all__ = [
    "Application",
    "AuthEvent",
    "ChatSession",
    "Contact",
    "CoverLetter",
    "EmailVerification",
    "Job",
    "OutreachMessage",
    "PasswordReset",
    "ReferralSuggestion",
    "RefreshToken",
    "Resume",
    "ResumeParsedData",
    "ResumeReview",
    "ResumeVersion",
    "SupervisorLog",
    "TailoredResume",
    "Tenant",
    "User",
    "UserProfile",
]
