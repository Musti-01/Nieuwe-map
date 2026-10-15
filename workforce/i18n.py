"""Local, explicit translations. No user data is sent to a translation service."""
import json
import re
import string
from contextvars import ContextVar
from pathlib import Path
from functools import lru_cache

LANGUAGES={'nl':'Nederlands','fr':'Français','en':'English','de':'Deutsch','es':'Español'}
_language=ContextVar('shiftflow_language',default='nl')

def set_language(language):
    if language not in LANGUAGES:
        raise ValueError('Unsupported language')
    _language.set(language)

@lru_cache(maxsize=1)
def catalogs():
    return json.loads(Path(__file__).with_name('translations.json').read_text())

def tr(message, **values):
    if not isinstance(message,str):
        return message
    language=_language.get()
    translated=catalogs().get(message,{}).get(language,message) if language!='nl' else message
    if language!='nl' and message not in catalogs() and not values:
        # Server validation errors contain formatted values. Match catalogued templates,
        # keeping every captured personal name/value unchanged.
        candidates = sorted(catalogs().items(), key=lambda item: len(re.sub(r'\{[^}]+\}', '', item[0])), reverse=True)
        for source, variants in candidates:
            if '{v' not in source or language not in variants or variants[language] == source:
                continue
            pattern = ''
            seen = set()
            for literal, field, _, _ in string.Formatter().parse(source):
                pattern += re.escape(literal)
                if field is not None:
                    pattern += '(?P=' + field + ')' if field in seen else '(?P<' + field + '>.*?)'
                    seen.add(field)
            match = re.fullmatch(pattern, message, re.DOTALL)
            if match:
                captured = match.groupdict()
                if source == '{v0}: vul 1 tot {v1} tekens in.':
                    captured['v0'] = tr(captured['v0'])
                try:
                    return variants[language].format(**captured)
                except (KeyError, ValueError):
                    continue
    return translated.format(**values) if values else translated

def translated_formatter(formatter):
    # Formatter literals are translated at their source; personal names stay untouched.
    return formatter

def translated_table(rows):
    if not isinstance(rows,list):
        return rows
    enum_columns={'status','role','rol','type','actie','naar','van','uitgeklokt'}
    return [{tr(k):tr(v) if k.lower() in enum_columns and isinstance(v,str) else v for k,v in row.items()} if isinstance(row,dict) else row for row in rows]
