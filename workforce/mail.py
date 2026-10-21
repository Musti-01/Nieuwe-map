"""Optional TLS SMTP worker. Decisions stay committed if delivery fails."""
import os
import ssl
import smtplib
import threading
import requests
import hashlib
from email.message import EmailMessage
from sqlalchemy import select, or_
from workforce.models import Notification
from workforce.service import now


def mail_configured():
    return bool(os.getenv('MAIL_FROM') and (os.getenv('RESEND_API_KEY') or all(os.getenv(k) for k in ('SMTP_HOST', 'SMTP_USER', 'SMTP_PASSWORD'))))


def deliver_pending(session_factory, limit=20):
    if not mail_configured():
        return {'configured': False, 'sent': 0, 'failed': 0}
    port = int(os.getenv('SMTP_PORT', '465'))
    if not os.getenv('RESEND_API_KEY') and port not in (465, 587):
        raise ValueError('Gebruik SMTP met TLS op poort 465 of STARTTLS op 587.')
    sent, failed = 0, 0
    with session_factory.begin() as s:
        notifications = list(s.scalars(select(Notification).where(Notification.sent_at.is_(None), Notification.attempts < 5, or_(Notification.expires_at.is_(None), Notification.expires_at > now())).order_by(Notification.id).limit(limit).with_for_update(skip_locked=True)))
        for n in notifications:
            n.attempts += 1
            message = EmailMessage()
            message['From'] = os.environ['MAIL_FROM']
            message['To'] = n.recipient
            message['Subject'] = n.subject
            message.set_content(n.body)
            try:
                if os.getenv('RESEND_API_KEY'):
                    namespace = hashlib.sha256(os.getenv('APP_BASE_URL', '').encode()).hexdigest()[:16]
                    response = requests.post('https://api.resend.com/emails',
                        headers={'Authorization': 'Bearer ' + os.environ['RESEND_API_KEY'],
                                 'Idempotency-Key': f'shiftflow-{namespace}-{n.id}'},
                        json={'from': os.environ['MAIL_FROM'], 'to': [n.recipient], 'subject': n.subject, 'text': n.body},
                        timeout=15, allow_redirects=False)
                    if not 200 <= response.status_code < 300:
                        raise OSError('Mail delivery failed')
                    n.sent_at = now()
                    n.body = 'Bericht verzonden.'
                    sent += 1
                    continue
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
                n.body = 'Bericht verzonden.'
                sent += 1
            except (smtplib.SMTPException, OSError, requests.RequestException):
                failed += 1
    if sent or failed:
        from workforce.operations import record_event
        record_event(session_factory, 'mail', 'delivery_failed' if failed else 'delivered')
    return {'configured': True, 'sent': sent, 'failed': failed}


def start_worker(session_factory):
    """One daemon per app process; row locks prevent duplicate concurrent deliveries."""
    if os.getenv('EMAIL_DELIVERY_ENABLED') != '1' or not mail_configured():
        return None
    stop = threading.Event()

    def work():
        from workforce.operations import report_error, maintenance
        cycles = 0
        while not stop.is_set():
            try:
                if os.getenv('EMAIL_DELIVERY_ENABLED') == '1' and mail_configured():
                    deliver_pending(session_factory)
                if cycles % 120 == 0:
                    maintenance(session_factory)
                cycles += 1
            except Exception as exc:
                report_error(session_factory, exc)
            stop.wait(30)
    threading.Thread(target=work, daemon=True, name='shiftflow-mail').start()
    return stop


if __name__ == '__main__':
    from workforce.db import make_engine, sessions
    result = deliver_pending(sessions(make_engine()))
    print(result)  # Counts only; no addresses, credentials or SMTP errors.
