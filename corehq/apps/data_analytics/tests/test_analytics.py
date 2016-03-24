from datetime import datetime
import uuid
from django.test import TestCase
from corehq.apps.data_analytics.analytics import get_app_submission_breakdown
from corehq.apps.sofabed.models import FormData
from corehq.util.test_utils import generate_cases
from dimagi.utils.dates import DateSpan


class MaltAnalyticsTest(TestCase):
    dependent_apps = [
        'corehq.apps.sofabed'
    ]

    @classmethod
    def setUpClass(cls):
        pass

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
    print combination_count_list
    domain = 'test-data-analytics'
    received = datetime(2016, 3, 24)
    month = DateSpan.from_month(3, 2016)
    for app, device, userid, username, count in combination_count_list:
        for i in range(count):
            _save_to_analytics_db(domain, received, app, device, userid, username)

    data_back = get_app_submission_breakdown(domain, month)
    normalized_data_back = set([_breakdown_dict_to_tuple(bdd) for bdd in data_back])
    self.assertEqual(set(combination_count_list), normalized_data_back)


def _save_to_analytics_db(domain, received, app, device, user_id, username):
    unused_args = {
        'time_start': received,
        'time_end': received,
        'duration': 1
    }
    FormData.objects.create(
        domain=domain,
        received_on=received,
        instance_id=uuid.uuid4().hex,
        app_id=app,
        device_id=device,
        user_id=user_id,
        username=username,
        **unused_args
    )


def _breakdown_dict_to_tuple(breakdown_dict):
    # convert the analytics response to the test's input format
    return (
        breakdown_dict['app_id'],
        breakdown_dict['device_id'],
        breakdown_dict['user_id'],
        breakdown_dict['username'],
        breakdown_dict['num_of_forms'],
    )
