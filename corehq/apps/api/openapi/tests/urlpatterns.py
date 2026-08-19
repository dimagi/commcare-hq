"""Converting Django URL patterns to OpenAPI-style paths, for tests that
compare what is routed against what is documented.

This conversion is necessarily lossy: a named group's internal character
class (e.g. ``[\\w\\-,]+`` for ``case_id``) is erased entirely, collapsed
into a bare ``{case_id}`` placeholder. So a route tightened to reject IDs
the docs imply are legal -- or loosened to accept more than the docs imply
-- stays invisible to a comparison built on this conversion; it only
catches a route and its docs disagreeing about *shape* (which segments
exist, which are parameters), not about what a parameter's value may
contain.
"""

import re

_GROUP_RE = re.compile(r'\(\?P<(\w+)>[^)]*\)')
_PLACEHOLDER_RE = re.compile(r'\{[^}]*\}')
_ESCAPED_CHAR_RE = re.compile(r'\\.')
_METACHARACTERS = r'.*+?[]()|^$\\'
_STRAY_METACHARACTER_RE = re.compile(f'[{re.escape(_METACHARACTERS)}]')


def pattern_to_relative_path(pattern, *, strict=True):
    """A Django url regex pattern as a plain OpenAPI-style path fragment,
    relative to whatever the pattern is included under.

    The trailing slash is optional in several hand-written case routes
    (``/?$``); the documented path always has it.

    With ``strict`` (the default), raises if a regex metacharacter this
    conversion doesn't know how to translate survives into the result --
    see ``_check_no_stray_metacharacters()``. Pass ``strict=False`` when
    walking patterns this module does not own (e.g. the whole app's
    resolved URLconf, in search of one known prefix) and cannot vouch
    for; the pair tests against ``corehq.apps.api.const`` -- the patterns
    this check actually protects -- use the strict default.
    """
    path = pattern.lstrip('^').rstrip('$')
    path = _GROUP_RE.sub(r'{\1}', path)
    if strict:
        _check_no_stray_metacharacters(pattern, path)
    path = path.replace(r'\.', '.')
    if path.endswith('/?'):
        path = path[:-1]
    return path


def _check_no_stray_metacharacters(original_pattern, path):
    """Fail loudly if a regex metacharacter survives this conversion
    unhandled.

    After named groups are collapsed into ``{param}`` placeholders, the
    only regex syntax this conversion still knows how to translate is an
    escaped literal (``\\.``, as in ``v0\\.6``) and a trailing ``/?``
    (optional trailing slash, stripped by the caller). Anything else from
    ``.*+?[]()|^$\\`` that survives here was silently ignored rather than
    translated -- e.g. an *unescaped* ``.``, which Django's router treats
    as "any character" but which this conversion would render as a
    literal dot in the documented path. A pattern like
    ``r'case/v2.0/?$'`` paired with the documented path
    ``'/a/{domain}/api/case/v2.0/'`` would pass a plain string-equality
    pair test today while also silently routing ``case/v2X0/`` -- exactly
    the kind of route/docs divergence this whole comparison exists to
    catch.
    """
    remainder = path
    if remainder.endswith('/?'):
        remainder = remainder[:-2] + '/'
    remainder = _ESCAPED_CHAR_RE.sub('', remainder)
    remainder = _PLACEHOLDER_RE.sub('', remainder)
    stray = _STRAY_METACHARACTER_RE.search(remainder)
    assert stray is None, (
        f'{original_pattern!r} converts to {path!r}, which still contains '
        f'the unhandled regex metacharacter {stray.group()!r} outside a '
        '{param} placeholder. pattern_to_relative_path() does not know '
        'how to translate it, so the Django route and the documented '
        'OpenAPI path can silently diverge.'
    )
