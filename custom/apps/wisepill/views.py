from datetime import datetime
from django.http import HttpResponse, HttpResponseBadRequest
from custom.apps.wisepill.models import WisePillDeviceEvent
from corehq.apps.sms.handlers.keyword import handle_structured_sms
from corehq.apps.sms.models import CommConnectCase
from corehq.apps.reminders.models import SurveyKeyword, METHOD_STRUCTURED_SMS
from corehq.apps.api.models import require_api_user_permission, PERMISSION_POST_WISEPILL

@require_api_user_permission(PERMISSION_POST_WISEPILL)
def device_data(request):
    if "data" not in request.POST:
        return HttpResponseBadRequest("Missing 'data' POST parameter.")
    
    data = request.POST.get("data")
    data = data.strip()
    data_points = data.split(",")
    device_id = None
    for data_point in data_points:
        key_value = data_point.partition("=")
        key = key_value[0].strip().upper()
        value = key_value[2].strip()
        if key == "SN":
            device_id = value
            break
    
    if device_id is None:
        return HttpResponseBadRequest("Missing 'SN' in data string.")
    
    # This view lookup is an implicit assert that either one device exists
    # with the given device_id, or no devices exist with this device_id.
    case = CommConnectCase.view("wisepill/device",
                                key=[device_id],
                                include_docs=True).one()
    
    event = WisePillDeviceEvent(
        domain=case.domain if case is not None else None,
        data=data,
        received_on=datetime.utcnow(),
        case_id=case._id if case is not None else None,
        processed=False,
    )
    event.save()
    
    if case is not None:
        survey_keywords = SurveyKeyword.get_all(case.domain)
        for survey_keyword in survey_keywords:
            if survey_keyword.keyword.upper() == "DEVICE_EVENT":
                for survey_keyword_action in survey_keyword.actions:
                    if survey_keyword_action.action == METHOD_STRUCTURED_SMS:
                        handle_structured_sms(survey_keyword, survey_keyword_action, case, None, "DEVICE_EVENT,%s" % data, send_response=False)
                        event.processed = True
                        event.save()
                        break
    
    return HttpResponse("")

