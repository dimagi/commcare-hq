import csv
from casexml.apps.case.models import CommCareCase
from datetime import datetime
from django.http import HttpResponse, HttpResponseBadRequest
from custom.apps.wisepill.models import WisePillDeviceEvent
from corehq.apps.sms.handlers.keyword import handle_structured_sms
from corehq.apps.sms.models import Keyword, KeywordAction
from corehq.apps.api.models import require_api_user_permission, PERMISSION_POST_WISEPILL
from corehq.apps.domain.decorators import require_superuser
from dimagi.utils.couch.database import iter_docs


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
    case = CommCareCase.view("wisepill/device",
                             key=[device_id],
                             include_docs=True).one()
    
    event = WisePillDeviceEvent(
        domain=case.domain if case is not None else None,
        data=data,
        received_on=datetime.utcnow(),
        case_id=case.case_id if case is not None else None,
        processed=False,
    )
    event.save()
    
    if case is not None:
        for survey_keyword in Keyword.get_by_domain(case.domain).filter(keyword__iexact="DEVICE_EVENT"):
            for survey_keyword_action in survey_keyword.keywordaction_set.all():
                if survey_keyword_action.action == KeywordAction.ACTION_STRUCTURED_SMS:
                    handle_structured_sms(survey_keyword, survey_keyword_action, case, None,
                        "DEVICE_EVENT,%s" % data, send_response=False)
                    event.processed = True
                    event.save()
                    break
    
    return HttpResponse("")


@require_superuser
def export_events(request):
    """
    Nothing fancy, just a simple csv dump of all the WisePill event
    data stored for debugging. This can't really be a domain-specific
    report because we may not be able to tie an event to a domain if
    the device was not configured properly in CommCareHQ.
    """
    attrs = [
        '_id',
        'domain',
        'data',
        'received_on',
        'case_id',
        'processed',
        'serial_number',
        'timestamp',
    ]
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="device_events.csv"'
    writer = csv.writer(response)
    writer.writerow(attrs)

    ids = WisePillDeviceEvent.get_all_ids()
    for doc in iter_docs(WisePillDeviceEvent.get_db(), ids):
        event = WisePillDeviceEvent.wrap(doc)
        writer.writerow([getattr(event, attr) for attr in attrs])

    return response
