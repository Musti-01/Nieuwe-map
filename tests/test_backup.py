import os
from unittest.mock import patch
import pytest
from workforce.backup import create_backup, verify_restore


def test_backup_rejects_weak_key_and_unsafe_restore_target(tmp_path):
    with pytest.raises(ValueError):
        create_backup('postgresql://localhost/unused', tmp_path, 'weak')
    with pytest.raises(ValueError):
        verify_restore(tmp_path/'absent.gpg', 'postgresql://localhost/production', 'strong-test-key-not-a-secret')


def test_backup_failure_removes_partial_archive(tmp_path):
    # Failure during encryption must never leave a downloadable partial backup.
    import subprocess
    from unittest.mock import Mock
    with patch('workforce.backup.postgres_command', return_value=(['fake'], {})), patch('workforce.backup.subprocess.run') as run:
        run.side_effect = [subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 1)]
        with pytest.raises(RuntimeError):
            create_backup('postgresql://localhost/unused', tmp_path, 'strong-test-key-not-a-secret')
    assert list(tmp_path.iterdir()) == []
