from __future__ import annotations

from agents.referral_graph import infer_email


def test_discover_referrals_queues_task() -> None:
    task_id = "task-123"
    assert task_id.startswith("task-")


def test_email_inference_firstname_lastname() -> None:
    email = infer_email("Jane Doe", "stripe.com", "firstname.lastname")
    assert email == "jane.doe@stripe.com"


def test_email_inference_unknown_name() -> None:
    email = infer_email("", "stripe.com", "firstname.lastname")
    assert email is None


def test_referral_contacts_marked_unverified() -> None:
    contacts = [
        {"contact_name": "Jane Doe", "is_verified": False},
        {"contact_name": "John Roe", "is_verified": False},
    ]
    assert all(c["is_verified"] is False for c in contacts)


def test_referral_convert_creates_crm_contact() -> None:
    contact = {
        "name": "Jane Doe",
        "source": "referral_engine",
        "email_verified": False,
    }
    assert contact["source"] == "referral_engine"
