"""Refresh application imports when Streamlit updates a running checkout."""
import hashlib
import importlib
from pathlib import Path
import sys
import threading


def prepare_release(root):
    """Keep Python modules and Streamlit resources on the same source revision.

    Removing the complete package avoids mixing ORM classes from separate
    declarative registries. Third-party modules and browser session state stay intact.
    The lock and release marker live outside watched project modules.
    """
    root = Path(root).resolve()
    lock = vars(sys).setdefault('_shiftflow_release_lock', threading.RLock())
    with lock:
        files = [root / name for name in ('cloud_app.py', 'cloud_bootstrap.py', 'app.py')]
        for directory in ('workforce', 'migrations'):
            files.extend(p for p in (root / directory).rglob('*') if p.suffix in ('.py', '.json'))
        digest = hashlib.sha256()
        for path in sorted(files):
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
        release = (str(root), digest.hexdigest())
        if getattr(sys, '_shiftflow_release', None) == release:
            return False
        worker_module = sys.modules.get('workforce.mail')
        for stop in getattr(worker_module, '_worker_stops', ()):
            stop.set()
        project_modules = [name for name in sys.modules if name == 'workforce' or name.startswith('workforce.')]
        if project_modules:
            import streamlit as st
            st.cache_resource.clear()
            for name in project_modules:
                sys.modules.pop(name, None)
        importlib.invalidate_caches()
        sys._shiftflow_release = release
        return True


def startup_error(exception):
    """Logging must still work if project imports or database setup are broken."""
    import logging
    import uuid
    # Reuse already-loaded monitoring only; never import a broken package.
    operations = sys.modules.get('workforce.operations')
    database = sys.modules.get('workforce.db')
    if operations is not None and database is not None:
        try:
            return operations.report_error(database.sessions(database.make_engine()), exception)
        except Exception:
            pass
    reference = uuid.uuid4().hex[:12]
    logging.getLogger('shiftflow.startup').error('ShiftFlow startup failed; reference=%s', reference)
    # Never import the failing application package or log exception contents here.
    return reference
