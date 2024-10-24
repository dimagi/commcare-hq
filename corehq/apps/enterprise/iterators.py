from datetime import datetime
from corehq.apps.es import filters
from corehq.apps.es.forms import FormES
from corehq.apps.enterprise.resumable_iterator_wrapper import ResumableIteratorWrapper


def raise_after_max_elements(it, max_elements, exception=None):
    for total_yielded, ele in enumerate(it):
        if total_yielded >= max_elements:
            exception = exception or Exception('Too Many Elements')
            raise exception

        yield ele


def get_enterprise_form_iterator(account, start_date, end_date, last_domain=None, last_time=None, last_id=None):
    domains = account.get_domains()

    it = multi_domain_form_generator(domains, start_date, end_date, last_domain, last_time, last_id)
    return ResumableIteratorWrapper(it, lambda ele: {
        'domain': ele['domain'],
        'received_on': ele['received_on'],
        'id': ele['form']['meta']['instanceID']
    })


def multi_domain_form_generator(domains, start_date, end_date, last_domain=None, last_time=None, last_id=None):
    domain_index = domains.index(last_domain) if last_domain else 0

    def _get_domain_iterator(last_time=None, last_id=None):
        if domain_index >= len(domains):
            return None
        domain = domains[domain_index]
        return domain_form_generator(domain, start_date, end_date, last_time, last_id)

    current_iterator = _get_domain_iterator(last_time, last_id)

    while current_iterator:
        yield from current_iterator
        domain_index += 1
        if domain_index >= len(domains):
            break
        current_iterator = _get_domain_iterator()


def domain_form_generator(domain, start_date, end_date, last_time=None, last_id=None):
    if not last_time:
        last_time = datetime.now()

    while True:
        query = create_domain_query(domain, start_date, end_date, last_time, last_id)
        results = query.run()
        for form in results.hits:
            last_form_fetched = form
            yield last_form_fetched

        if len(results.hits) >= results.total:
            break
        else:
            last_time = last_form_fetched['received_on']
            last_id = last_form_fetched['_id']


def create_domain_query(domain, start_date, end_date, last_time, last_id):
    CURSOR_SIZE = 5

    query = (
        FormES()
        .domain(domain)
        .user_type('mobile')
        .submitted(gte=start_date, lte=end_date)
        .size(CURSOR_SIZE)
    )

    query.es_query['sort'] = [
        {'received_on': {'order': 'desc'}},
        {'form.meta.instanceID': 'asc'}
    ]

    if last_id:
        query = query.filter(filters.OR(
            filters.AND(
                filters.term('received_on', last_time),
                filters.range_filter('form.meta.instanceID', gt=last_id)
            ),
            filters.range_filter('received_on', lt=last_time)
        ))
    else:
        query = query.submitted(lte=last_time)

    return query
