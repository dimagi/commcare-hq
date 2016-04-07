import uuid
from django.test import TestCase
from corehq.apps.performance_sms import dbaccessors
from corehq.apps.performance_sms.dbaccessors import delete_all_configs
from corehq.apps.performance_sms.models import PerformanceConfiguration


class TestPerformanceDbaccessors(TestCase):
    dependent_apps = ['corehq.couchapps']

    def test_by_domain(self):
        domain = uuid.uuid4().hex
        config = _make_performance_config(domain)

        results = dbaccessors.by_domain(domain)
        self.assertEqual(1, len(results))
        self.assertEqual(config._id, results[0]._id)

        # check no results for some other domain
        no_results = dbaccessors.by_domain(uuid.uuid4().hex)
        self.assertEqual(0, len(no_results))

    def tearDown(self):
        delete_all_configs()


def _make_performance_config(domain):
    config = PerformanceConfiguration(domain=domain, recipient_id=uuid.uuid4().hex, template='test')
    config.save()
    return config
