from __future__ import absolute_import
from __future__ import unicode_literals
import re


def next_available_name(prefix, existing_names):
    '''
    Given a set of names like ['foo-1', 'foo-2'],
    figure out the largest suffix in use and return a name
    that's one larger. Does not densely pack names, so
    ['foo-1', 'foo-3'] will return 'foo-4', not 'foo-2'.
    '''
    max_suffix = 0
    for name in existing_names:
        match = re.search(r'-([0-9]+)$', name)
        if match:
            max_suffix = max(max_suffix, int(match.group(1)))
    return prefix + '-' + str(max_suffix + 1)
