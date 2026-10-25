"""Encrypted PostgreSQL backups. Credentials never enter command arguments or logs."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import tempfile
import uuid
from sqlalchemy import text, inspect
from sqlalchemy.engine import make_url
from alembic.config import Config
from alembic.script import ScriptDirectory
from workforce.db import make_engine


def postgres_command(url, tool, *arguments):
    parsed = make_url(url)
    if not parsed.database or not parsed.host:
        raise ValueError('Use an explicit PostgreSQL host and database')
    engine = make_engine(url)
    try:
        with engine.connect() as connection:
            major = int(connection.scalar(text('SHOW server_version_num'))) // 10000
    finally:
        engine.dispose()
    if major not in (16, 17, 18):
        raise ValueError('Supported PostgreSQL versions: 16, 17, 18')
    env = os.environ.copy()
    fields = {'PGHOST': parsed.host, 'PGPORT': str(parsed.port or 5432), 'PGDATABASE': parsed.database,
              'PGUSER': parsed.username or '', 'PGPASSWORD': parsed.password or '',
              'PGSSLMODE': parsed.query.get('sslmode', 'prefer' if parsed.host in ('localhost', '127.0.0.1', '::1') else 'verify-full')}
    # Local certificate files cannot be implicitly mounted into a helper container.
    if set(parsed.query) - {'sslmode', 'channel_binding', 'connect_timeout', 'application_name'}:
        raise ValueError('Use provider-managed backups when custom connection options are required')
    fields['PGCHANNELBINDING'] = parsed.query.get('channel_binding', 'prefer')
    fields['PGCONNECT_TIMEOUT'] = '20'
    env.update(fields)
    command = ['docker', 'run', '--rm', '-i', '--network=host']
    for key in fields:
        command += ['--env', key]
    return command + [f'postgres:{major}', tool, *arguments], env


def create_backup(url, output_dir, passphrase):
    if not isinstance(passphrase, str) or len(passphrase) < 20:
        raise ValueError('Use a backup passphrase of at least 20 characters')
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    name = datetime.now(timezone.utc).strftime('shiftflow-%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8] + '.dump.gpg'
    target = output_dir / name
    command, env = postgres_command(url, 'pg_dump', '--format=custom', '--no-owner', '--no-acl')
    try:
        with tempfile.TemporaryDirectory() as temporary:
            plain = Path(temporary) / 'database.dump'
            with plain.open('xb') as output:
                os.chmod(plain, 0o600)
                result = subprocess.run(command, env=env, stdout=output, stderr=subprocess.PIPE)
            if result.returncode:
                raise RuntimeError('PostgreSQL backup failed; no backup published')
            with target.open('xb') as output:
                os.chmod(target, 0o600)
                result = subprocess.run(['gpg', '--no-options', '--homedir', temporary, '--batch', '--pinentry-mode', 'loopback',
                    '--passphrase-fd', '0', '--symmetric', '--cipher-algo', 'AES256', '--output', '-', str(plain)],
                    input=passphrase.encode(), stdout=output, stderr=subprocess.PIPE)
            if result.returncode:
                raise RuntimeError('Backup encryption failed; no backup published')
        return target
    except Exception:
        target.unlink(missing_ok=True)
        raise


def verify_restore(archive, target_url, passphrase):
    """Restore only into an empty, explicitly named disposable database."""
    if not (make_url(target_url).database or '').endswith('_restore_test'):
        raise ValueError('Restore verification requires a separate *_restore_test database')
    engine = make_engine(target_url)
    try:
        if inspect(engine).get_table_names():
            raise ValueError('Restore verification database must be empty')
    finally:
        engine.dispose()
    command, env = postgres_command(target_url, 'pg_restore', '--exit-on-error', '--no-owner', '--no-acl', '--dbname', make_url(target_url).database)
    with tempfile.TemporaryDirectory() as temporary:
        plain = Path(temporary) / 'restore.dump'
        with plain.open('xb') as output:
            os.chmod(plain, 0o600)
            result = subprocess.run(['gpg', '--no-options', '--homedir', temporary, '--batch', '--pinentry-mode', 'loopback',
                '--passphrase-fd', '0', '--decrypt', str(archive)], input=passphrase.encode(), stdout=output, stderr=subprocess.PIPE)
        if result.returncode:
            raise RuntimeError('Backup decryption failed')
        with plain.open('rb') as source:
            result = subprocess.run(command, env=env, stdin=source, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if result.returncode:
            raise RuntimeError('Backup restore failed')
    engine = make_engine(target_url)
    try:
        with engine.connect() as connection:
            revision = connection.scalar(text('SELECT version_num FROM alembic_version'))
            counts = {table: connection.scalar(text(f'SELECT count(*) FROM {table}'))
                      for table in ('users', 'branches', 'work_entries', 'absences', 'sick_notes', 'salary_rates')}
        config = Config()
        config.set_main_option('script_location', str(Path(__file__).resolve().parent.parent / 'migrations'))
        if revision != ScriptDirectory.from_config(config).get_current_head():
            raise RuntimeError('Restored schema version did not match')
        return counts
    finally:
        engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', default='.local/backups')
    parser.add_argument('--verify-archive')
    args = parser.parse_args()
    try:
        if args.verify_archive:
            print({'restored_counts': verify_restore(args.verify_archive, os.environ['RESTORE_DATABASE_URL'], os.environ['BACKUP_PASSPHRASE'])})
        else:
            print(create_backup(os.environ['DATABASE_URL'], args.output_dir, os.environ['BACKUP_PASSPHRASE']).name)
    except Exception:
        # Provider errors can include credentials; expose no exception text.
        print('Backup operation failed. Check the configuration; no credentials were logged.')
        raise SystemExit(1)
