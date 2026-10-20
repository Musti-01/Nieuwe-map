"""Validate private attachments without trusting browser MIME types or filenames."""
from io import BytesIO
from pathlib import PurePosixPath
import warnings
from PIL import Image, UnidentifiedImageError

MAX_SIZE = 5 * 1024 * 1024
INVALID_FILE = 'Upload een geldig PDF-, PNG- of JPG-bestand van maximaal 5 MB.'


def validate_note(filename, content):
    if not isinstance(filename, str) or not isinstance(content, bytes) or not 0 < len(content) <= MAX_SIZE:
        raise ValueError(INVALID_FILE)
    filename = PurePosixPath(filename.replace('\\', '/')).name
    if not filename or len(filename) > 120 or any(ord(c) < 32 or ord(c) == 127 for c in filename):
        raise ValueError(INVALID_FILE)
    suffix = PurePosixPath(filename).suffix.lower()
    if suffix == '.pdf':
        if not content.startswith(b'%PDF-') or not content.rstrip().endswith(b'%%EOF'):
            raise ValueError(INVALID_FILE)
        return filename, 'application/pdf'
    expected = {'.png': ('PNG', 'image/png'), '.jpg': ('JPEG', 'image/jpeg'), '.jpeg': ('JPEG', 'image/jpeg')}.get(suffix)
    if not expected:
        raise ValueError(INVALID_FILE)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                if image.format != expected[0]:
                    raise ValueError(INVALID_FILE)
                image.verify()
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError(INVALID_FILE) from exc
    return filename, expected[1]
