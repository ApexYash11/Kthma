"""Controlled execution layer (ADR 0003): Simulator default, Razorpay fail-closed."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ExecutionRequest:
    recovery_case_id: str
    action: str
    amount: int
    approved: bool


@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    adapter: str
    detail: str


class Executor(Protocol):
    def execute(self, request: ExecutionRequest) -> ExecutionResult: ...


class SimulatorExecutor:
    """Labelled simulator. Never presented as a real Razorpay call (ADR 0003)."""

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        if not request.approved:
            return ExecutionResult(False, "SIMULATOR", "blocked: policy approval missing")
        if request.action == "do_nothing":
            return ExecutionResult(False, "SIMULATOR", "no action to execute")
        # Deterministic simulation: interventions on repeated failures would be wasteful.
        success = request.action in {"payment_link", "retry_subscription", "retry_payment", "reminder"}
        detail = "simulated execution succeeded" if success else "simulated execution failed"
        return ExecutionResult(success, "SIMULATOR", detail)


class GroundedSimulatorExecutor(SimulatorExecutor):
    """Simulator grounded in the synthetic world: an action succeeds only when the
    world (ground truth) says the case was actually recoverable. Decision never
    sees this mapping; Verification is the world's response."""

    def __init__(self, world: dict[str, bool]) -> None:
        self.world = world

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        result = super().execute(request)
        if result.success and not self.world.get(request.recovery_case_id, False):
            return ExecutionResult(
                False, "SIMULATOR", "simulated world: payment did not complete"
            )
        return result


class RazorpayExecutor:
    """Razorpay Test Mode path. Fails closed without keys (ADR 0003, ADR 0005)."""

    def __init__(self) -> None:
        self.key_id = os.environ.get("RAZORPAY_KEY_ID", "")
        self.key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")

    @property
    def configured(self) -> bool:
        return bool(self.key_id and self.key_secret)

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        if not self.configured:
            raise RuntimeError(
                "fail closed: RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET not set; use SimulatorExecutor"
            )
        if not request.approved:
            return ExecutionResult(False, "RAZORPAY_TEST_MODE", "blocked: policy approval missing")
        raise RuntimeError(
            "Razorpay Test Mode client not wired yet; research file docs/research/razorpay-test-mode.md pending"
        )


class RazorpayPaymentLinkTransport:
    """HTTP transport for the verified Payment Links API (see docs/research)."""

    BASE_URL = "https://api.razorpay.com"

    def __init__(self, key_id: str, key_secret: str, timeout: float = 10.0) -> None:
        if not key_id or not key_secret:
            raise RuntimeError(
                "fail closed: RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET not set; use SimulatorExecutor"
            )
        self.key_id = key_id
        self.key_secret = key_secret
        self.timeout = timeout

    def _auth_header(self) -> str:
        import base64

        raw = f"{self.key_id}:{self.key_secret}".encode()
        return "Basic " + base64.b64encode(raw).decode()

    def request(self, method: str, path: str, payload: dict) -> dict:
        import json as _json
        from urllib import request as _request

        req = _request.Request(
            self.BASE_URL + path,
            data=_json.dumps(payload).encode(),
            headers={
                "Authorization": self._auth_header(),
                "Content-Type": "application/json",
            },
            method=method,
        )
        with _request.urlopen(req, timeout=self.timeout) as resp:
            return _json.loads(resp.read().decode())


class HybridRazorpayExecutor:
    """Per the research split: payment_link/reminder -> real Test Mode API;
    retry_payment/retry_subscription -> labelled Simulator (no Razorpay endpoint
    exists for merchant-side retries). Batch paths stay on the pure simulator
    because of the 30-link Test Mode cap."""

    def __init__(self, transport: RazorpayPaymentLinkTransport) -> None:
        self.transport = transport
        self._simulator = SimulatorExecutor()

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        if not request.approved:
            return ExecutionResult(False, "RAZORPAY_TEST_MODE", "blocked: policy approval missing")
        if request.action in {"retry_payment", "retry_subscription"}:
            return self._simulator.execute(request)
        if request.action not in {"payment_link", "reminder"}:
            return ExecutionResult(False, "RAZORPAY_TEST_MODE", f"unsupported action: {request.action}")
        try:
            response = self.transport.request(
                "POST",
                "/v1/payment_links",
                {
                    "amount": request.amount * 100,  # rupees -> paise (verified doc)
                    "currency": "INR",
                    "accept_partial": False,
                    "reference_id": request.recovery_case_id,  # <=40 chars
                    "customer": {
                        "name": "Demo Merchant Customer",
                        "email": "customer@example.com",
                        "contact": "+919000000000",
                    },
                    "notify": {"sms": True, "email": True},
                    "reminder_enable": request.action == "reminder",
                    "notes": {"recovery_case_id": request.recovery_case_id},
                },
            )
        except Exception as exc:  # surface as failed execution, never crash the operator flow
            return ExecutionResult(False, "RAZORPAY_TEST_MODE", f"razorpay error: {exc}")
        return ExecutionResult(
            True,
            "RAZORPAY_TEST_MODE",
            f"payment link created: {response['id']} {response.get('short_url', '')}",
        )

