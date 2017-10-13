from celery.task import task
from corehq.apps.hqcase.utils import bulk_update_cases
from dimagi.utils.chunked import chunked


@task(queue='background_queue', ignore_result=True)
def process_payment_confirmations(domain, payment_confirmations):
    for chunk in chunked(payment_confirmations, 100):
        bulk_update_cases(domain, [
            (update.case_id, update.properties, False)
            for update in chunk
        ], "custom.enikshay.integrations.bets.views.payment_confirmation")
