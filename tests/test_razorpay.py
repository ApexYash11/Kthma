"""Razorpay payment-link executor: real Test Mode API behind a transport seam."""

import pytest

from kthma.execution import (
    ExecutionRequest,
    HybridRazorpayExecutor,
    RazorpayPaymentLinkTransport,
)


class FakeTransport:
    def __init__(self):
        self.calls = []
        self.response = {"id": "plink_123", "short_url": "https://rzp.io/i/abc", "status": "created"}

    def request(self, method: str, path: str, payload: dict) -> dict:
        self.calls.append((method, path, payload))
        return self.response


def _executor():
    return HybridRazorpayExecutor(transport=FakeTransport())


def test_payment_link_action_creates_real_link_via_transport():
    executor = _executor()
    result = executor.execute(ExecutionRequest("rc_00042", "payment_link", 2499, approved=True))
    assert result.success is True
    assert result.adapter == "RAZORPAY_TEST_MODE"
    assert "plink_123" in result.detail


def test_amount_is_converted_to_paise_and_reference_id_is_case_id():
    executor = _executor()
    executor.execute(ExecutionRequest("rc_00042", "payment_link", 2499, approved=True))
    method, path, payload = executor.transport.calls[0]
    assert (method, path) == ("POST", "/v1/payment_links")
    assert payload["amount"] == 249900  # paise, per Razorpay docs
    assert payload["currency"] == "INR"
    assert payload["reference_id"] == "rc_00042"
    assert payload["accept_partial"] is False
    assert payload["notify"] == {"sms": True, "email": True}


def test_reminder_action_also_uses_payment_link_with_reminders_enabled():
    executor = _executor()
    result = executor.execute(ExecutionRequest("rc_1", "reminder", 999, approved=True))
    assert result.success is True
    assert executor.transport.calls[0][2]["reminder_enable"] is True


def test_retry_actions_stay_on_the_labelled_simulator():
    executor = _executor()
    result = executor.execute(ExecutionRequest("rc_1", "retry_payment", 2499, approved=True))
    assert result.adapter == "SIMULATOR"
    assert executor.transport.calls == []  # no network call for retries


def test_unapproved_action_is_blocked_before_any_network_call():
    executor = _executor()
    result = executor.execute(ExecutionRequest("rc_1", "payment_link", 2499, approved=False))
    assert result.success is False
    assert executor.transport.calls == []


def test_transport_error_surfaces_as_failed_execution_not_crash():
    class FailingTransport:
        def request(self, method, path, payload):
            raise RuntimeError("razorpay 400: amount is not a whole number")

    executor = HybridRazorpayExecutor(transport=FailingTransport())
    result = executor.execute(ExecutionRequest("rc_1", "payment_link", 2499, approved=True))
    assert result.success is False
    assert "400" in result.detail


def test_real_transport_builds_basic_auth_request():
    import base64

    transport = RazorpayPaymentLinkTransport(key_id="rzp_test_k", key_secret="s")
    assert transport._auth_header() == "Basic " + base64.b64encode(b"rzp_test_k:s").decode()
