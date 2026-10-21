import smtplib
from unittest.mock import MagicMock
from sqlalchemy import select
from workforce.mail import deliver_pending
from workforce.models import Notification
from datetime import timedelta
from workforce.service import now


def test_mail_optional_without_credentials(api, team, monkeypatch):
    for key in ['SMTP_HOST', 'SMTP_USER', 'SMTP_PASSWORD', 'MAIL_FROM']:
        monkeypatch.delenv(key, raising=False)
    assert deliver_pending(api.sessions) == {'configured': False, 'sent': 0, 'failed': 0}
    with api.sessions() as s:
        assert all(n.sent_at is None for n in s.scalars(select(Notification)))


def test_mail_tls_retry_and_delivered_once(api, team, monkeypatch):
    for key, value in {'SMTP_HOST': 'smtp.example.test', 'SMTP_USER': 'test-user', 'SMTP_PASSWORD': 'test-only', 'MAIL_FROM': 'platform@example.test', 'SMTP_PORT': '465'}.items():
        monkeypatch.setenv(key, value)
    client = MagicMock()
    client.__enter__.return_value = client
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(smtplib, 'SMTP_SSL', factory)
    client.send_message.side_effect = smtplib.SMTPException('Test error')
    assert deliver_pending(api.sessions)['failed'] == 4
    client.send_message.side_effect = None
    assert deliver_pending(api.sessions)['sent'] == 4
    assert factory.call_args.kwargs['context'].verify_mode.name == 'CERT_REQUIRED'
    assert deliver_pending(api.sessions)['sent'] == 0
    with api.sessions() as s:
        assert all(n.sent_at and n.attempts == 2 for n in s.scalars(select(Notification)))


def test_resend_https_delivery_retry_and_redaction(api, team, monkeypatch):
    monkeypatch.setenv('RESEND_API_KEY', 'test-key')
    monkeypatch.setenv('MAIL_FROM', 'platform@example.test')
    monkeypatch.setenv('APP_BASE_URL', 'https://shiftflow.example')
    post = MagicMock()
    post.return_value.status_code = 503
    monkeypatch.setattr('workforce.mail.requests.post', post)
    assert deliver_pending(api.sessions)['failed'] == 4
    first_key = post.call_args_list[0].kwargs['headers']['Idempotency-Key']
    post.reset_mock()
    post.return_value.status_code = 200
    assert deliver_pending(api.sessions)['sent'] == 4
    assert post.call_args_list[0].kwargs['headers']['Idempotency-Key'] == first_key
    assert post.call_args.args[0] == 'https://api.resend.com/emails'
    assert post.call_args.kwargs['allow_redirects'] is False
    with api.sessions() as session:
        assert all(n.body == 'Bericht verzonden.' for n in session.scalars(select(Notification)))
    assert deliver_pending(api.sessions)['sent'] == 0


def test_expired_mail_and_retry_limit(api, team, monkeypatch):
    monkeypatch.setenv('RESEND_API_KEY', 'test-key')
    monkeypatch.setenv('MAIL_FROM', 'platform@example.test')
    with api.sessions.begin() as session:
        for n in session.scalars(select(Notification)):
            n.expires_at = now()-timedelta(seconds=1)
    post = MagicMock()
    monkeypatch.setattr('workforce.mail.requests.post', post)
    assert deliver_pending(api.sessions)['sent'] == 0
    post.assert_not_called()
