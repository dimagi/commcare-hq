from collections import defaultdict
from django.db.models import Count
from .models import FormData


def get_form_counts_by_user_xmlns(domain, startdate, enddate, user_ids=None,
                                  xmlnss=None, by_submission_time=True):
    date_field = 'received_on' if by_submission_time else 'time_end'
    query = (FormData.objects
             .filter(domain=domain,
                     **{'{}__gte'.format(date_field): startdate,
                        '{}__lt'.format(date_field): enddate})
             .values('xmlns', 'user_id', 'app_id')
             .annotate(count=Count('pk')))

    if user_ids:
        query = query.filter(user_id__in=user_ids)
    if xmlnss:
        query = query.filter(xmlns__in=xmlnss)

    return defaultdict(lambda: 0, {
        (r['user_id'], r['xmlns'], r['app_id']): r['count'] for r in query
    })
