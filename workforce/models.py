from datetime import datetime, timezone
from sqlalchemy import (String, ForeignKey, DateTime, Boolean, Integer, Index,
                        CheckConstraint, ForeignKeyConstraint, text)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    platform_owner: Mapped[bool] = mapped_column(Boolean, default=False)
    platform_admin: Mapped[bool] = mapped_column(Boolean, default=False)

class ApprovalFields:
    status: Mapped[str] = mapped_column(String(20), default="pending")
    address: Mapped[str] = mapped_column(String(255))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class Organization(ApprovalFields, Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    chain: Mapped[str] = mapped_column(String(120))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    contact_phone: Mapped[str] = mapped_column(String(40))
    __table_args__ = (CheckConstraint("status IN ('pending', 'approved', 'rejected', 'blocked')", name="organization_status"),)
    primary_color: Mapped[str] = mapped_column(String(7), default="#E31837")
    secondary_color: Mapped[str] = mapped_column(String(7), default="#006491")

class Branch(ApprovalFields, Base):
    __tablename__ = "branches"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    __table_args__ = (CheckConstraint("status IN ('pending', 'approved', 'rejected', 'blocked')", name="branch_status"),)
    # Commercial metadata only: no payments or package enforcement in this MVP.
    plan: Mapped[str] = mapped_column(String(30), default="starter")

class Membership(Base):
    __tablename__ = "memberships"
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20))
    __table_args__ = (CheckConstraint("role IN ('admin', 'employee', 'revoked')", name="valid_role"),)

class WorkEntry(Base):
    __tablename__ = "work_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_status: Mapped[str] = mapped_column(String(20), default="pending")
    version: Mapped[int] = mapped_column(Integer, default=1)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("review_status IN ('pending', 'approved')", name="shift_review_status"),
        CheckConstraint("review_status != 'approved' OR (ended_at IS NOT NULL AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)", name="approved_shift_complete"),
        ForeignKeyConstraint(["branch_id", "user_id"], ["memberships.branch_id", "memberships.user_id"]),
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="valid_interval"),
        Index("one_active_entry_per_user", "user_id", unique=True, postgresql_where=text("ended_at IS NULL")),
    )

class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class LoginLimit(Base):
    __tablename__ = "login_limits"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class Audit(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"))
    action: Mapped[str] = mapped_column(String(80))
    detail: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class ApprovalDecision(Base):
    __tablename__ = "approval_decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"))
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    previous_status: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(500))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("approval_decisions.id"), unique=True)
    recipient: Mapped[str] = mapped_column(String(254))
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(2000))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)

class ShiftReview(Base):
    __tablename__ = "shift_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("work_entries.id"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(500))
    old_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    old_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    new_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    new_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    previous_status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
