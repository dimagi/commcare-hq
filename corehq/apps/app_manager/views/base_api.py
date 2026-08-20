from django.http import JsonResponse

from corehq.apps.app_manager.views.single_form_api import _status_for_result


def errors_response(result):
    return JsonResponse(
        {'errors': [error.to_json() for error in result.errors]},
        status=_status_for_result(result),
    )
