from django.core.management import call_command
from django.test import SimpleTestCase

from corehq.apps.es.sms import sms_adapter  # any valid adapter will do
from corehq.apps.es.tests.utils import es_test


@es_test(requires=[sms_adapter], setup_class=True)
class TestUpdateEsMapping(SimpleTestCase):
    """Guard against future changes to the `update_es_mapping` management
    command accidentally breaking this migration utility.
    """

    def test_update_es_mapping(self):
        """Ensure the management command succeeds"""
        call_command("update_es_mapping", sms_adapter.index_name, noinput=True)

    def test_update_es_mapping_quiet(self):
        """Ensure the management command succeeds with --quiet"""
        call_command("update_es_mapping", sms_adapter.index_name, "--quiet", noinput=True)
