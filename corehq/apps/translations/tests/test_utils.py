from __future__ import absolute_import
from __future__ import unicode_literals

import doctest

from corehq.apps.translations import utils


def test_doctests():
    results = doctest.testmod(utils)
    assert results.failed == 0
