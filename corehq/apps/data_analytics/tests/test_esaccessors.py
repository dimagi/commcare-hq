from datetime import datetime

from django.test import SimpleTestCase

from dimagi.utils.dates import DateSpan

from corehq.apps.data_analytics.esaccessors import (
    get_app_submission_breakdown_es,
)
from corehq.apps.data_analytics.tests.utils import save_to_es_analytics_db
from corehq.apps.es.forms import form_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.util.test_utils import generate_cases


@es_test(requires=[form_adapter])
class MaltAnalyticsTest(SimpleTestCase):
    pass


@generate_cases([
    ([
        # differentiate by userid
        ('app', 'device', 'userid0', 1),
        ('app', 'device', 'userid1', 2),
    ], ),
    ([
        # differentiate by device
        ('app', 'device0', 'userid', 1),
        ('app', 'device1', 'userid', 2),
    ], ),
    ([
        # differentiate by app
        ('app0', 'device', 'userid', 1),
        ('app1', 'device', 'userid', 2),
    ], ),
], MaltAnalyticsTest)
def test_app_submission_breakdown(self, combination_count_list):
    """
    The breakdown of this report is (app, device, userid): count
    """
    domain = 'test-data-analytics'
    received = datetime(2016, 3, 24)
    month = DateSpan.from_month(3, 2016)
    for app, device, userid, count in combination_count_list:
        for i in range(count):
            save_to_es_analytics_db(domain, received, app, device, userid, 'test-user')

    data_back = get_app_submission_breakdown_es(domain, month)
    normalized_data_back = set(data_back)
    self.assertEqual(set(combination_count_list), normalized_data_back)
