from datetime import datetime, timedelta
from django.utils.translation import gettext as _
from corehq.apps.es import filters
from corehq.apps.es.utils import es_format_datetime
from corehq.apps.es.forms import FormES
from corehq.apps.enterprise.exceptions import TooMuchRequestedDataError
from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain


def raise_after_max_elements(it, max_elements, exception=None):
    for total_yielded, ele in enumerate(it):
        if total_yielded >= max_elements:
            exception = exception or Exception('Too Many Elements')
            raise exception

        yield ele


class IterableEnterpriseFormQuery:
    '''
    A class representing a query that returns its results as an iterator
    The intended use case is to support queries that cross pagination boundaries
    '''
    def __init__(self, account, start_date, end_date, last_domain, last_time, last_id):
        MAX_DATE_RANGE_DAYS = 100
        (self.start_date, self.end_date) = resolve_start_and_end_date(start_date, end_date, MAX_DATE_RANGE_DAYS)
        self.account = account
        self.last_domain = last_domain
        self.last_time = last_time
        self.last_id = last_id

    def execute(self, limit=None):
        domains = self.account.get_domains()

        it = multi_domain_form_generator(
            domains,
            self.start_date,
            self.end_date,
            self.last_domain,
            self.last_time,
            self.last_id,
            limit=limit
        )

        xform_converter = RawFormConverter()
        return (xform_converter.convert(form) for form in it)

    @classmethod
    def get_kwargs_from_map(cls, map):
        last_domain = map.get('domain', None)
        last_time = map.get('received_on', None)
        if last_time:
            last_time = datetime.fromisoformat(last_time)
        last_id = map.get('id', None)
        return {
            'last_domain': last_domain,
            'last_time': last_time,
            'last_id': last_id
        }

    @classmethod
    def get_query_params(cls, fetched_object):
        return {
            'domain': fetched_object['domain'],
            'received_on': fetched_object['submitted'],
            'id': fetched_object['form_id']
        }


def resolve_start_and_end_date(start_date, end_date, maximum_date_range):
    '''
    Provide start and end date values if not supplied.
    '''
    if not end_date:
        end_date = datetime.utcnow()

    if not start_date:
        start_date = end_date - timedelta(days=30)

    if end_date - start_date > timedelta(days=maximum_date_range):
        raise TooMuchRequestedDataError(
            _('Date ranges with more than {} days are not supported').format(maximum_date_range)
        )

    return start_date, end_date


class RawFormConverter:
    def __init__(self):
        self.app_lookup = AppIdToNameResolver()

    def convert(self, form):
        domain = form['domain']
        submitted_date = datetime.strptime(form['received_on'][:19], '%Y-%m-%dT%H:%M:%S')

        return {
            'form_id': form['form']['meta']['instanceID'],
            'form_name': form['form']['@name'] or _('Unnamed'),
            'submitted': submitted_date,
            'app_name': self.app_lookup.resolve_app_id_to_name(domain, form['app_id']) or _('App not found'),
            'username': form['form']['meta']['username'],
            'domain': domain
        }


class AppIdToNameResolver:
    def __init__(self):
        self.domain_lookup_tables = {}

    def resolve_app_id_to_name(self, domain, app_id):
        if 'domain' not in self.domain_lookup_tables:
            domain_apps = get_brief_apps_in_domain(domain)
            self.domain_lookup_tables[domain] = {a.id: a.name for a in domain_apps}

        return self.domain_lookup_tables[domain].get(app_id, None)


def multi_domain_form_generator(
        domains, start_date, end_date, last_domain=None, last_time=None, last_id=None, limit=None):
    domain_index = domains.index(last_domain) if last_domain else 0

    remaining = limit

    def _get_domain_iterator(last_time=None, last_id=None):
        if domain_index >= len(domains):
            return None
        domain = domains[domain_index]
        return domain_form_generator(domain, start_date, end_date, last_time, last_id, limit=remaining)

    current_iterator = _get_domain_iterator(last_time, last_id)

    while current_iterator:
        for form in current_iterator:
            yield form
            if remaining:
                remaining -= 1
                if remaining == 0:
                    return
        domain_index += 1
        if domain_index >= len(domains):
            return
        current_iterator = _get_domain_iterator()


def domain_form_generator(domain, start_date, end_date, last_time=None, last_id=None, limit=None):
    if not last_time:
        last_time = datetime.now()

    remaining = limit

    while True:
        query = create_domain_forms_query(domain, start_date, end_date, last_time, last_id, limit=remaining)
        results = query.run()
        for form in results.hits:
            last_form_fetched = form
            yield last_form_fetched

        num_fetched = len(results.hits)

        if num_fetched >= results.total or (remaining and num_fetched >= remaining):
            break
        else:
            if remaining:
                remaining -= num_fetched
                assert remaining > 0
            last_time = last_form_fetched['received_on']
            last_id = last_form_fetched['_id']


def create_domain_forms_query(domain, start_date, end_date, last_time, last_id, limit=None):
    query = (
        FormES()
        .domain(domain)
        .user_type('mobile')
        .submitted(gte=start_date, lte=end_date)
    )

    if limit:
        query = query.size(limit)

    query.es_query['sort'] = [
        {'inserted_at': {'order': 'desc'}},
        {'doc_id': 'asc'}
    ]

    if last_id:
        query = query.filter(filters.OR(
            filters.AND(
                filters.term('inserted_at', es_format_datetime(last_time)),
                filters.range_filter('doc_id', gt=last_id)
            ),
            filters.date_range('inserted_at', lt=last_time)
        ))
    else:
        query = query.inserted(lte=last_time)

    return query
