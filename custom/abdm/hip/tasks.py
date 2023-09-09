from custom.abdm.utils import task, ABDM_QUEUE


@task(queue=ABDM_QUEUE)
def process_hip_consent_notification_request(request_data):
    from custom.abdm.hip.views.consents import GatewayConsentRequestNotifyProcessor
    GatewayConsentRequestNotifyProcessor(request_data).process_request()


@task(queue=ABDM_QUEUE)
def process_health_information_request(request_data):
    from custom.abdm.hip.views.health_information import GatewayHealthInformationRequestProcessor
    GatewayHealthInformationRequestProcessor(request_data).process_request()
