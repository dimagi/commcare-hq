from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
from corehq.apps.reports.tasks import _convert_legacy_indices_to_export_properties
from corehq.util.test_utils import generate_cases


class IndicesConversionTest(SimpleTestCase):
    """
    Ensures that export indices map correctly to question ids
    """


@generate_cases([
    (['form.outer.inner'], set(['outer-inner'])),
    (['form.outer.inner', 'outer.inner'], set(['outer-inner'])),
    (['form.outer.inner', None, ''], set(['outer-inner'])),

], IndicesConversionTest)
def test_convert_legacy_indices_to_export_properties(self, indices, expected):
    self.assertEqual(
        _convert_legacy_indices_to_export_properties(indices),
        expected,
    )
