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
