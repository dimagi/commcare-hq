from contextlib import contextmanager

from corehq.apps.es import case_adapter
from corehq.apps.es.tests.utils import es_test


@es_test(requires=[case_adapter], setup_class=True)
class TestGetGeohashes:

    @staticmethod
    @contextmanager
    def eleven_cases():
        pass

    @staticmethod
    @contextmanager
    def eleven_thousand_cases():
        pass

    def test_finding_precision_11k(self):
        with self.eleven_thousand_cases():
            pass

    def test_finding_precision_11(self):
        with self.eleven_cases():
            pass
