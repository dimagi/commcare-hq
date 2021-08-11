from io import BytesIO

from django.test.client import Client

from corehq.util.soft_assert import soft_assert
from corehq.util.test_utils import unit_testing_only

legacy_notification_assert = soft_assert(notify_admins=True, exponential_backoff=False)


@unit_testing_only
def spoof_submission(submit_url, body):
    client = Client()
    f = BytesIO(body.encode('utf-8'))
    f.name = 'form.xml'
    response = client.post(submit_url, {
        'xml_submission_file': f,
    })
    try:
        return response['X-CommCareHQ-FormID']
    except KeyError:
        return None
