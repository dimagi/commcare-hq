from collections import defaultdict
from django.db.models import Count
from corehq.apps.es.aggregations import MultiTermAggregation, AggregationTerm, TermsAggregation
from corehq.apps.es.forms import FormES
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
    previous_term = None
    for name, field in reversed(terms):
        term = TermsAggregation(name, field)
        if previous_term is not None:
            term = term.aggregation(previous_term)
        previous_term = term
    query = query.aggregation(term)

    def _add_terms(aggregation_bucket, term, remaining_terms, current_counts, current_key=None):
        for bucket in getattr(aggregation_bucket, term.name).buckets_list:
            key = (bucket.key,) if current_key is None else current_key + (bucket.key,)
            if remaining_terms:
                _add_terms(bucket, remaining_terms[0], remaining_terms[1:], current_counts, current_key=key)
            else:
                # base case
                current_counts[key] += bucket.doc_count

    counts = defaultdict(lambda: 0)
    _add_terms(query.run().aggregations, terms[0], terms[1:], current_counts=counts)
    return counts


def _get_app_submission_breakdown_es(domain_name, monthspan):
    query = FormES().domain(domain_name).submitted(
        gte=monthspan.startdate,
        lt=monthspan.computed_enddate,
    ).aggregation(MultiTermAggregation(
        name='breakdown',
        terms=[
            AggregationTerm('app_id', 'app_id'),
            AggregationTerm('device_id', 'form.meta.deviceID'),
            AggregationTerm('user_id', 'form.meta.userID'),
            AggregationTerm('username', 'form.meta.username'),
        ]
    ))
    return query.run().aggregations.breakdown.get_buckets()
