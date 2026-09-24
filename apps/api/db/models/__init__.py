"""Model exports for metadata registration."""

from db.models.application import Application
from db.models.application_timeline import ApplicationTimelineEvent
from db.models.application_campaign_stage import ApplicationCampaignStage
from db.models.alert_log import AlertLog
from db.models.automation_log import AutomationLog
from db.models.auth_event import AuthEvent
from db.models.browser_agent_artifact import BrowserAgentArtifact
from db.models.browser_agent_event_log import BrowserAgentEventLog
from db.models.browser_agent_pause_request import BrowserAgentPauseRequest
from db.models.browser_agent_run import BrowserAgentRun
from db.models.browser_agent_selector_memory import BrowserAgentSelectorMemory
from db.models.browser_agent_state_snapshot import BrowserAgentStateSnapshot
from db.models.browser_agent_step import BrowserAgentStep
from db.models.chat_session import ChatSession
from db.models.company_crawl_target import CompanyCrawlTarget
from db.models.chat_message import ChatMessage
from db.models.chat_summary import ChatSummary
from db.models.contact import Contact
from db.models.cover_letter import CoverLetter
from db.models.dedup_log import DedupLog
from db.models.email_verification import EmailVerification
from db.models.embedding_job import EmbeddingJob
from db.models.employer_account import EmployerAccount
from db.models.h1b_sponsor import H1BSponsor
from db.models.ingestion_metric import IngestionMetric
from db.models.job import Job
from db.models.job_requirement import JobRequirement
from db.models.outreach import OutreachMessage
from db.models.password_reset import PasswordReset
from db.models.referral import ReferralSuggestion
from db.models.ranking_feedback import RankingFeedback
from db.models.refresh_token import RefreshToken
from db.models.resume_parsed_data import ResumeParsedData
from db.models.resume_review import ResumeReview
from db.models.resume_version import ResumeVersion
from db.models.resume import Resume, TailoredResume
from db.models.screening_answer import ScreeningAnswer
from db.models.supervisor_log import SupervisorLog
from db.models.stream_processing_log import StreamProcessingLog
from db.models.tenant import Tenant
from db.models.user import User
from db.models.user_preference import UserPreference
from db.models.user_saved_job import UserSavedJob
from db.models.user_profile import UserProfile
from db.models.opt_tracker import OptTracker

__all__ = [
    "Application",
    "ApplicationTimelineEvent",
    "ApplicationCampaignStage",
    "AlertLog",
    "AutomationLog",
    "AuthEvent",
    "BrowserAgentArtifact",
    "BrowserAgentEventLog",
    "BrowserAgentPauseRequest",
    "BrowserAgentRun",
    "BrowserAgentSelectorMemory",
    "BrowserAgentStateSnapshot",
    "BrowserAgentStep",
    "ChatSession",
    "CompanyCrawlTarget",
    "ChatMessage",
    "ChatSummary",
    "Contact",
    "CoverLetter",
    "DedupLog",
    "EmailVerification",
    "EmbeddingJob",
    "EmployerAccount",
    "H1BSponsor",
    "IngestionMetric",
    "Job",
    "JobRequirement",
    "OutreachMessage",
    "PasswordReset",
    "ReferralSuggestion",
    "RankingFeedback",
    "RefreshToken",
    "Resume",
    "ResumeParsedData",
    "ResumeReview",
    "ResumeVersion",
    "ScreeningAnswer",
    "SupervisorLog",
    "StreamProcessingLog",
    "TailoredResume",
    "Tenant",
    "User",
    "UserPreference",
    "UserSavedJob",
    "UserProfile",
    "OptTracker",
]
