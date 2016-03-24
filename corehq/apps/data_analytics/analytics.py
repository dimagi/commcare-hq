from django.db.models import Count
from corehq.apps.sofabed.models import FormData


def get_app_submission_breakdown(domain_name, monthspan):
    """
    Returns one row for every app, device, userid, username tuple, along with the number of
    forms submitted for that tuple.
    """
    start_date = monthspan.computed_startdate
    end_date = monthspan.computed_enddate
    forms_query = FormData.objects.filter(
        domain=domain_name,
        received_on__range=(start_date, end_date)
    )
    return forms_query.values('app_id', 'device_id', 'user_id', 'username').annotate(
        num_of_forms=Count('instance_id')
    )
