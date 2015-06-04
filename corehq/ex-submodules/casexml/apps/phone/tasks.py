from celery import task
from casexml.apps.phone.data_providers import get_long_running_providers


@task
def async_restore_response(restore_state):
    response = restore_state.restore_class()
    long_running_providers = get_long_running_providers()
    for provider in long_running_providers:
        partial_response = provider.get_response(restore_state)
        response = response + partial_response
        partial_response.close()

    return response
