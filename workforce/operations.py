"""Bounded operational events without exception messages or personal data."""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete
from workforce.models import SystemEvent, SickNote, Notification

logger = logging.getLogger('shiftflow.operations')


def record_event(session_factory, category, code):
    if category not in ('error', 'mail', 'backup', 'maintenance') or not isinstance(code, str) or len(code) > 80:
        raise ValueError('Invalid operational event')
    with session_factory.begin() as session:
        session.add(SystemEvent(category=category, code=code, occurred_at=datetime.now(timezone.utc)))


def report_error(session_factory, exception):
    # Exception strings, tracebacks, SQL parameters, reset URLs and documents are never logged.
    from sqlalchemy.exc import SQLAlchemyError
    reference = uuid.uuid4().hex[:12]
    code = ('database_error' if isinstance(exception, SQLAlchemyError) else 'unexpected_error') + ':' + reference
    logger.error('ShiftFlow incident %s', code)
    try:
        record_event(session_factory, 'error', code)
    except Exception:
        logger.error('ShiftFlow incident store unavailable; reference=%s', reference)
    return reference


def maintenance(session_factory):
    now = datetime.now(timezone.utc)
    with session_factory.begin() as session:
        removed = session.execute(delete(SickNote).where(SickNote.expires_at <= now)).rowcount
        session.execute(delete(Notification).where(Notification.expires_at <= now, Notification.sent_at.is_(None)))
        session.execute(delete(SystemEvent).where(SystemEvent.occurred_at < now-timedelta(days=30)))
        session.add(SystemEvent(category='maintenance', code='completed', occurred_at=now))
    return removed


if __name__ == '__main__':
    from workforce.db import make_engine, sessions
    print({'removed_documents': maintenance(sessions(make_engine()))})
