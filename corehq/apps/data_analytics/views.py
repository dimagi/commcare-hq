from corehq.apps.data_analytics.models import MALTRow
from corehq.apps.data_analytics.admin import MALTRowAdmin
from dimagi.utils.django.management import export_as_csv_action


def malt_csv_response(month, year):
    query_month = "{year}-{month}-01".format(year=year, month=month)
    queryset = MALTRow.objects.filter(month=query_month)
    return export_as_csv_action(exclude=['id'])(MALTRowAdmin, None, queryset)
