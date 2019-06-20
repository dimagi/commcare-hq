from __future__ import absolute_import
from __future__ import unicode_literals

import doctest

from .. import chunked


def test_doctests():
    results = doctest.testmod(chunked)
    assert results.failed == 0, results
