from custom.abdm.exceptions import ABDMServiceUnavailable
from custom.abdm.utils import task, ABDM_QUEUE

# TODO Handle any error for background jobs
# TODO Handle gateway errors for background jobs
# Note In case of gateway exceptions , it is stored in celery task result (if configured)


@task(queue=ABDM_QUEUE)
def sample_background_task(request_data):
    print("Background job started", request_data)
    import time
    time.sleep(10)
    raise ABDMServiceUnavailable()
    print("Background job completed")


@task(queue=ABDM_QUEUE)
def process_hiu_consent_notification_request(request_data):
    from custom.abdm.hip.views.consents import GatewayConsentRequestNotifyProcessor
    GatewayConsentRequestNotifyProcessor(request_data).process_request()
