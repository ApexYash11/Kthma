"""SQLite persistence for SplitDataset: features vs ground truth stores."""

from dataclasses import dataclass

from sqlalchemy import Boolean, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from kthma import GroundTruth, RecoveryCaseFeatures, SplitDataset

SPLITS = ("development", "holdout")


class Base(DeclarativeBase):
    pass


class FeatureRow(Base):
    __tablename__ = "features"

    recovery_case_id: Mapped[str] = mapped_column(String, primary_key=True)
    split: Mapped[str] = mapped_column(String)
    leakage_type: Mapped[str] = mapped_column(String)
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String)
    payment_method: Mapped[str] = mapped_column(String)
    failure_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer)
    last_attempt_at: Mapped[str] = mapped_column(String)
    customer_id: Mapped[str] = mapped_column(String)
    prior_successful_payments: Mapped[int] = mapped_column(Integer)
    prior_failures: Mapped[int] = mapped_column(Integer)
    days_since_last_success: Mapped[int] = mapped_column(Integer)
    subscription_flag: Mapped[bool] = mapped_column(Boolean)
    checkout_entered_flag: Mapped[bool] = mapped_column(Boolean)


class GroundTruthRow(Base):
    __tablename__ = "ground_truth"

    recovery_case_id: Mapped[str] = mapped_column(String, primary_key=True)
    split: Mapped[str] = mapped_column(String)
    recoverable: Mapped[bool] = mapped_column(Boolean)
    best_action: Mapped[str] = mapped_column(String)
    expected_outcome: Mapped[int] = mapped_column(Integer)
    amount: Mapped[int] = mapped_column(Integer)
    intended_scenario: Mapped[str] = mapped_column(String)


class ExecutionRow(Base):
    """Persisted audit trail of every recovery action taken.

    Keyed by recovery_case_id so that approve is idempotent: a second approve
    on the same case returns the stored row instead of executing again.
    """

    __tablename__ = "executions"

    recovery_case_id: Mapped[str] = mapped_column(String, primary_key=True)
    action: Mapped[str] = mapped_column(String)
    adapter: Mapped[str] = mapped_column(String)
    success: Mapped[bool] = mapped_column(Boolean)
    detail: Mapped[str] = mapped_column(String)
    approved_at: Mapped[str] = mapped_column(String)
    verification_outcome: Mapped[str] = mapped_column(String)
    recovered_amount: Mapped[int] = mapped_column(Integer)


def _engine(db_path: str):
    return create_engine(f"sqlite:///{db_path}")


def save_split(dataset: SplitDataset, db_path: str) -> None:
    engine = _engine(db_path)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.query(FeatureRow).delete()
        session.query(GroundTruthRow).delete()
        for split_name, split in (("development", dataset.development), ("holdout", dataset.holdout)):
            for f in split.features:
                session.add(
                    FeatureRow(
                        recovery_case_id=f.recovery_case_id,
                        split=split_name,
                        leakage_type=f.leakage_type,
                        amount=f.amount,
                        currency=f.currency,
                        payment_method=f.payment_method,
                        failure_reason=f.failure_reason,
                        attempt_count=f.attempt_count,
                        last_attempt_at=f.last_attempt_at,
                        customer_id=f.customer_id,
                        prior_successful_payments=f.prior_successful_payments,
                        prior_failures=f.prior_failures,
                        days_since_last_success=f.days_since_last_success,
                        subscription_flag=f.subscription_flag,
                        checkout_entered_flag=f.checkout_entered_flag,
                    )
                )
            for g in split.ground_truth:
                session.add(
                    GroundTruthRow(
                        recovery_case_id=g.recovery_case_id,
                        split=split_name,
                        recoverable=g.recoverable,
                        best_action=g.best_action,
                        expected_outcome=g.expected_outcome,
                        amount=g.amount,
                        intended_scenario=g.intended_scenario,
                    )
                )
        session.commit()


def load_features(db_path: str, split: str) -> tuple[RecoveryCaseFeatures, ...]:
    if split not in SPLITS:
        raise ValueError(f"unknown split: {split!r}")
    engine = _engine(db_path)
    with Session(engine) as session:
        rows = session.scalars(
            select(FeatureRow).where(FeatureRow.split == split).order_by(FeatureRow.recovery_case_id)
        ).all()
        return tuple(
            RecoveryCaseFeatures(
                recovery_case_id=r.recovery_case_id,
                leakage_type=r.leakage_type,
                amount=r.amount,
                currency=r.currency,
                payment_method=r.payment_method,
                failure_reason=r.failure_reason,
                attempt_count=r.attempt_count,
                last_attempt_at=r.last_attempt_at,
                customer_id=r.customer_id,
                prior_successful_payments=r.prior_successful_payments,
                prior_failures=r.prior_failures,
                days_since_last_success=r.days_since_last_success,
                subscription_flag=r.subscription_flag,
                checkout_entered_flag=r.checkout_entered_flag,
            )
            for r in rows
        )


def load_ground_truth(db_path: str, split: str) -> tuple[GroundTruth, ...]:
    if split not in SPLITS:
        raise ValueError(f"unknown split: {split!r}")
    engine = _engine(db_path)
    with Session(engine) as session:
        rows = session.scalars(
            select(GroundTruthRow)
            .where(GroundTruthRow.split == split)
            .order_by(GroundTruthRow.recovery_case_id)
        ).all()
        return tuple(
            GroundTruth(
                recovery_case_id=r.recovery_case_id,
                recoverable=r.recoverable,
                best_action=r.best_action,
                expected_outcome=r.expected_outcome,
                amount=r.amount,
                intended_scenario=r.intended_scenario,
            )
            for r in rows
        )


@dataclass(frozen=True)
class ExecutionRecord:
    recovery_case_id: str
    action: str
    adapter: str
    success: bool
    detail: str
    approved_at: str
    verification_outcome: str
    recovered_amount: int


def save_execution(db_path: str, record: ExecutionRecord) -> None:
    """Persist an execution row. Idempotent: calling twice for the same case
    overwrites the row rather than duplicating it."""
    engine = _engine(db_path)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        existing = session.get(ExecutionRow, record.recovery_case_id)
        if existing is None:
            session.add(
                ExecutionRow(
                    recovery_case_id=record.recovery_case_id,
                    action=record.action,
                    adapter=record.adapter,
                    success=record.success,
                    detail=record.detail,
                    approved_at=record.approved_at,
                    verification_outcome=record.verification_outcome,
                    recovered_amount=record.recovered_amount,
                )
            )
        else:
            existing.action = record.action
            existing.adapter = record.adapter
            existing.success = record.success
            existing.detail = record.detail
            existing.approved_at = record.approved_at
            existing.verification_outcome = record.verification_outcome
            existing.recovered_amount = record.recovered_amount
        session.commit()


def load_execution(db_path: str, recovery_case_id: str) -> ExecutionRecord | None:
    engine = _engine(db_path)
    with Session(engine) as session:
        row = session.get(ExecutionRow, recovery_case_id)
        if row is None:
            return None
        return ExecutionRecord(
            recovery_case_id=row.recovery_case_id,
            action=row.action,
            adapter=row.adapter,
            success=row.success,
            detail=row.detail,
            approved_at=row.approved_at,
            verification_outcome=row.verification_outcome,
            recovered_amount=row.recovered_amount,
        )


def load_all_executions(db_path: str) -> dict[str, ExecutionRecord]:
    engine = _engine(db_path)
    with Session(engine) as session:
        rows = session.scalars(select(ExecutionRow)).all()
        return {
            r.recovery_case_id: ExecutionRecord(
                recovery_case_id=r.recovery_case_id,
                action=r.action,
                adapter=r.adapter,
                success=r.success,
                detail=r.detail,
                approved_at=r.approved_at,
                verification_outcome=r.verification_outcome,
                recovered_amount=r.recovered_amount,
            )
            for r in rows
        }
