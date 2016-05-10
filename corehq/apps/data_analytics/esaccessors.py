from corehq.apps.es.aggregations import AggregationTerm, NestedTermAggregationsHelper
from corehq.apps.es.forms import FormES


def get_app_submission_breakdown_es(domain_name, monthspan):
    terms = [
        AggregationTerm('app_id', 'app_id'),
        AggregationTerm('device_id', 'form.meta.deviceID'),
        AggregationTerm('user_id', 'form.meta.userID'),
        AggregationTerm('username', 'form.meta.username'),
    ]
    query = FormES().domain(domain_name).submitted(
        gte=monthspan.startdate,
        lt=monthspan.computed_enddate,
    )
    return NestedTermAggregationsHelper(base_query=query, terms=terms).get_data()
