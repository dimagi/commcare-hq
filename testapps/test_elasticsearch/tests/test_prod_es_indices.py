from django.conf import settings
from django.test import SimpleTestCase
from corehq.pillows.utils import get_all_expected_es_indices


class ProdIndexManagementTest(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        cls._PILLOWTOPS = settings.PILLOWTOPS
        if not settings.PILLOWTOPS:
            # assumes HqTestSuiteRunner, which blanks this out and saves a copy here
            settings.PILLOWTOPS = settings._PILLOWTOPS

    @classmethod
    def tearDownClass(cls):
        settings.PILLOWTOPS = cls._PILLOWTOPS

    def test_prod_config(self):
        found_prod_indices = [info.to_json() for info in get_all_expected_es_indices()]
        for info in found_prod_indices:
            # for now don't test these two properties, just ensure they exist
            self.assertTrue(info['meta'])
            del info['meta']
            self.assertTrue(info['mapping'])
            del info['mapping']
        found_prod_indices = sorted(found_prod_indices, key=lambda info: info['index'])
        self.assertEqual(EXPECTED_PROD_INDICES, found_prod_indices)


EXPECTED_PROD_INDICES = [
    {
        "alias": "case_search",
        "index": "test_case_search_2016-03-15",
        "type": "case"
    },
    {
        "alias": "hqapps",
        "index": "test_hqapps_2016-10-20_1835",
        "type": "app"
    },
    {
        "alias": "hqcases",
        "index": "test_hqcases_2016-03-04",
        "type": "case"
    },
    {
        "alias": "hqdomains",
        "index": "test_hqdomains_2016-08-08",
        "type": "hqdomain"
    },
    {
        "alias": "hqgroups",
        "index": "test_hqgroups_20150403_1501",
        "type": "group"
    },
    {
        "alias": "hqusers",
        "index": "test_hqusers_2016-09-29",
        "type": "user"
    },
    {
        "alias": "ledgers",
        "index": "test_ledgers_2016-03-15",
        "type": "ledger"
    },
    {
        "alias": "report_cases",
        "index": "test_report_cases_czei39du507m9mmpqk3y01x72a3ux4p0",
        "type": "report_case"
    },
    {
        "alias": "report_xforms",
        "index": "test_report_xforms_20160824_1708",
        "type": "report_xform"
    },
    {
        "alias": "smslogs",
        "index": "test_smslogs_2017-02-09",
        "type": "sms"
    },
    {
        "alias": "xforms",
        "index": "test_xforms_2016-07-07",
        "type": "xform"
    }
]
