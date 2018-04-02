from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
from django.test import SimpleTestCase
from corehq.apps.data_analytics.esaccessors import get_app_submission_breakdown_es
from corehq.apps.data_analytics.tests.utils import save_to_es_analytics_db
from corehq.elastic import get_es_new
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import generate_cases
from dimagi.utils.dates import DateSpan
from pillowtop.es_utils import initialize_index_and_mapping
from six.moves import range


class MaltAnalyticsTest(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(MaltAnalyticsTest, cls).setUpClass()
        cls.es = get_es_new()

    def setUp(self):
        super(MaltAnalyticsTest, self).setUp()
        ensure_index_deleted(XFORM_INDEX_INFO.index)
        initialize_index_and_mapping(self.es, XFORM_INDEX_INFO)


@generate_cases([
    ([
         # differentiate by username
         ('app', 'device', 'userid', 'username0', 1),
         ('app', 'device', 'userid', 'username1', 2),
     ],),
    ([
         # differentiate by userid
         ('app', 'device', 'userid0', 'username', 1),
         ('app', 'device', 'userid1', 'username', 2),
     ],),
    ([
         # differentiate by device
         ('app', 'device0', 'userid', 'username', 1),
         ('app', 'device1', 'userid', 'username', 2),
     ],),
    ([
         # differentiate by app
         ('app0', 'device', 'userid', 'username', 1),
         ('app1', 'device', 'userid', 'username', 2),
     ],),
], MaltAnalyticsTest)
def test_app_submission_breakdown(self, combination_count_list):
    """
    The breakdown of this report is (app, device, userid, username): count
    """
    domain = 'test-data-analytics'
    received = datetime(2016, 3, 24)
    month = DateSpan.from_month(3, 2016)
    for app, device, userid, username, count in combination_count_list:
        for i in range(count):
            save_to_es_analytics_db(domain, received, app, device, userid, username)

    self.es.indices.refresh(XFORM_INDEX_INFO.index)
    data_back = get_app_submission_breakdown_es(domain, month)
    normalized_data_back = set(data_back)
    self.assertEqual(set(combination_count_list), normalized_data_back)
