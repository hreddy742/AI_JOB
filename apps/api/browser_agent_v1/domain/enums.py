"""State and status enums for Browser Agent V1."""

from __future__ import annotations

from enum import StrEnum


class BrowserAgentState(StrEnum):
    LANDING_PAGE = "LANDING_PAGE"
    CAREERS_LIST = "CAREERS_LIST"
    JOB_DETAIL = "JOB_DETAIL"
    APPLY_ENTRY = "APPLY_ENTRY"
    LOGIN = "LOGIN"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    SIGNUP = "SIGNUP"
    SIGNUP_REQUIRED = "SIGNUP_REQUIRED"
    SIGNUP_SUCCESS = "SIGNUP_SUCCESS"
    ACCOUNT_ALREADY_EXISTS = "ACCOUNT_ALREADY_EXISTS"
    ACCOUNT_RECOVERY_REQUIRED = "ACCOUNT_RECOVERY_REQUIRED"
    EMAIL_VERIFY_WAIT = "EMAIL_VERIFY_WAIT"
    PROFILE_FORM = "PROFILE_FORM"
    RESUME_UPLOAD = "RESUME_UPLOAD"
    SCREENING_QUESTIONS = "SCREENING_QUESTIONS"
    WORK_AUTHORIZATION = "WORK_AUTHORIZATION"
    REVIEW = "REVIEW"
    CAPTCHA_REQUIRED = "CAPTCHA_REQUIRED"
    MFA_REQUIRED = "MFA_REQUIRED"
    MANUAL_HELP_REQUIRED = "MANUAL_HELP_REQUIRED"
    READY_TO_SUBMIT = "READY_TO_SUBMIT"
    SUBMITTED = "SUBMITTED"
    FAILED = "FAILED"


class BrowserAgentRunStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BrowserAgentPauseStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class BrowserAgentStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class BrowserAgentActor(StrEnum):
    SYSTEM = "system"
    WORKER = "worker"
    USER = "user"
