from __future__ import absolute_import, unicode_literals

from corehq import toggles
from corehq.toggles import ALL_TAGS


def test_toggle_properties():
    """
    Check toggle properties
    """
    for toggle in toggles.all_toggles():
        assert toggle.slug
        assert toggle.label, 'Toggle "{}" label missing'.format(toggle.slug)
        assert toggle.tag, 'Toggle "{}" tag missing'.format(toggle.slug)
        assert toggle.tag in ALL_TAGS, 'Toggle "{}" tag "{}" unrecognized'.format(toggle.slug, toggle.tag)
        assert toggle.namespaces, 'Toggle "{}" namespaces missing'.format(toggle.slug)


def test_solutions_sub_tags():
    """
    Check Solutions sub-tags begin with 'Solutions - '

    Client side toggle filtering logic currently depends on "Solutions" being in these tag names.
    For context, see https://github.com/dimagi/commcare-hq/pull/24575#discussion_r293995391
    """
    solutions_tags = [toggles.TAG_SOLUTIONS_OPEN, toggles.TAG_SOLUTIONS_CONDITIONAL, toggles.TAG_SOLUTIONS_LIMITED]
    for tag in solutions_tags:
        assert tag.name.startswith('Solutions - ')
