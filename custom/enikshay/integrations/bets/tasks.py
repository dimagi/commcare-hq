from __future__ import absolute_import
import json
from celery.task import task
from corehq.apps.hqcase.utils import bulk_update_cases
from dimagi.utils.chunked import chunked
from dimagi.utils.logging import notify_exception

PAYMENT_CONFIRMATION_FAILURE = """BETS_PAYMENT_CONFIRMATION_FAILURE:
Updating payment confirmations failed. We need to manually reconcile failed
records any time this happens. This error message should include the complete
chunk of payment confirmations that were to be processed.
"""


@task(queue='background_queue', ignore_result=True)
def process_payment_confirmations(domain, payment_confirmations):
    for chunk in chunked(payment_confirmations, 100):
        try:
            bulk_update_cases(domain, [
                (update.case_id, update.properties, False)
                for update in chunk
            ], "custom.enikshay.integrations.bets.views.payment_confirmation")
        except Exception as e:
            notify_exception(
                request=None,
                message=PAYMENT_CONFIRMATION_FAILURE,
                details=json.dumps([update.to_json() for update in chunk]),
            )
