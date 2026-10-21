from datetime import date, datetime, timezone
from sqlalchemy import (String, ForeignKey, DateTime, Boolean, Integer, Index,
                        CheckConstraint, ForeignKeyConstraint, LargeBinary, Date, text)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(2), default="nl")
    __table_args__ = (CheckConstraint("language IN ('nl', 'fr', 'en', 'de', 'es')", name="user_language"),)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
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
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    # Commercial metadata only: no payments or package enforcement in this MVP.
    plan: Mapped[str] = mapped_column(String(30), default="starter")

class Membership(Base):
    __tablename__ = "memberships"
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20))
    __table_args__ = (CheckConstraint("role IN ('admin', 'employee', 'revoked')", name="valid_role"),)

class Absence(Base):
    __tablename__ = "absences"
    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    kind: Mapped[str] = mapped_column(String(10))
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(12))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (
        ForeignKeyConstraint(["branch_id", "user_id"], ["memberships.branch_id", "memberships.user_id"]),
        CheckConstraint("ends_on >= starts_on", name="absence_interval"),
        CheckConstraint("kind IN ('sick', 'leave')", name="absence_kind"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected', 'cancelled')", name="absence_status"),
    )

class SystemEvent(Base):
    __tablename__ = "system_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(20))
    code: Mapped[str] = mapped_column(String(80))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

class SickNote(Base):
    __tablename__ = "sick_notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    absence_id: Mapped[int | None] = mapped_column(ForeignKey("absences.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    filename: Mapped[str] = mapped_column(String(120))
    media_type: Mapped[str] = mapped_column(String(40))
    content: Mapped[bytes] = mapped_column(LargeBinary)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(["branch_id", "user_id"], ["memberships.branch_id", "memberships.user_id"]),
        CheckConstraint("octet_length(content) BETWEEN 1 AND 5242880", name="sick_note_size"),
        CheckConstraint("media_type IN ('application/pdf', 'image/png', 'image/jpeg')", name="sick_note_type"),
    )

class WorkEntry(Base):
    __tablename__ = "work_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("shift_plans.id"), unique=True)
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
    decision_id: Mapped[int | None] = mapped_column(ForeignKey("approval_decisions.id"), unique=True)
    recipient: Mapped[str] = mapped_column(String(254))
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(2000))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

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

class AccountToken(Base):
    __tablename__ = "account_tokens"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(254))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("purpose IN ('invite', 'reset')", name="account_token_purpose"),)

class ShiftPlan(Base):
    __tablename__ = "shift_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    note: Mapped[str] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (ForeignKeyConstraint(["branch_id", "user_id"], ["memberships.branch_id", "memberships.user_id"]), CheckConstraint("ends_at > starts_at", name="plan_interval"), CheckConstraint("status IN ('scheduled', 'cancelled')", name="plan_status"))
