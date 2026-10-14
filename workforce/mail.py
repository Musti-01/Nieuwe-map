"""Optional TLS SMTP worker. Decisions stay committed if delivery fails."""
import os
import ssl
import smtplib
from email.message import EmailMessage
from sqlalchemy import select
from workforce.models import Notification
from workforce.service import now


def deliver_pending(session_factory, limit=20):
    required = ['SMTP_HOST', 'SMTP_USER', 'SMTP_PASSWORD', 'MAIL_FROM']
    if not all(os.getenv(key) for key in required):
        return {'configured': False, 'sent': 0, 'failed': 0}
    port = int(os.getenv('SMTP_PORT', '465'))
    if port not in (465, 587):
        raise ValueError('Gebruik SMTP met TLS op poort 465 of STARTTLS op 587.')
    sent, failed = 0, 0
    with session_factory.begin() as s:
        notifications = list(s.scalars(select(Notification).where(Notification.sent_at.is_(None)).order_by(Notification.id).limit(limit).with_for_update(skip_locked=True)))
        for n in notifications:
            n.attempts += 1
            message = EmailMessage()
            message['From'] = os.environ['MAIL_FROM']
            message['To'] = n.recipient
            message['Subject'] = n.subject
            message.set_content(n.body)
            try:
                context = ssl.create_default_context()
                if port == 465:
                    client = smtplib.SMTP_SSL(os.environ['SMTP_HOST'], port, timeout=15, context=context)
                else:
                    client = smtplib.SMTP(os.environ['SMTP_HOST'], port, timeout=15)
                with client:
                    if port == 587:
                        client.starttls(context=context)
                    client.login(os.environ['SMTP_USER'], os.environ['SMTP_PASSWORD'])
                    client.send_message(message)
                n.sent_at = now()
                sent += 1
            except (smtplib.SMTPException, OSError):
                failed += 1
    return {'configured': True, 'sent': sent, 'failed': failed}

if __name__ == '__main__':
    from workforce.db import make_engine, sessions
    result = deliver_pending(sessions(make_engine()))
    print(result)  # Counts only; no addresses, credentials or SMTP errors.
