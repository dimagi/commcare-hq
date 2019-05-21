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
