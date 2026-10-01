import re

from flask_babel import gettext

FORBIDDEN = re.compile(r'[@/,:{}]|[\x00-\x1f\x7f]')
MAX_LEN   = 100
RESERVED  = ('.', '..')
MESSAGE   = 'A name cannot contain @ / , : { or }'


def name_error(name) -> str:
    if not isinstance(name, str) or not name.strip():
        return gettext('Give it a name')
    name = name.strip()
    if name in RESERVED:
        return gettext('That name is reserved')
    if len(name) > MAX_LEN:
        return gettext('Keep the name to %(max)d characters or fewer', max=MAX_LEN)
    if FORBIDDEN.search(name):
        return gettext('A name cannot contain any of these characters: %(chars)s', chars='@ / , : { }')
    return ''


def valid(name) -> bool:
    return not name_error(name)
