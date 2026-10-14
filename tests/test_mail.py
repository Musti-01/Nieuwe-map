import smtplib
from unittest.mock import MagicMock
from sqlalchemy import select
from workforce.mail import deliver_pending
from workforce.models import Notification


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
