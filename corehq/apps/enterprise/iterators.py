from abc import ABC, abstractmethod
from itertools import dropwhile, chain, islice
from datetime import datetime, timedelta, timezone
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
    - form_converter: an instance of a `EnterpriseDataConverter`
    that knows how to translate the iteration results and interpret the previous progress arguments
    - `start_date`: a date to start the date range. Can be None
    - `end_date`: the inclusive date to finish the date range. Can be None
    `last_domain`, `last_time`, and `last_id` are intended to represent the last result from a previous query
    that should now be resumed.
    - `last_domain`: the domain to resume the query on
    - `last_time`: the timestamp from the last result of the previous query
    - `last_id`: the id from the last result of the previous query
    '''
    def __init__(self, account, form_converter, start_date, end_date, last_domain, last_time, last_id):
        MAX_DATE_RANGE_DAYS = 100
        (self.start_date, self.end_date) = resolve_start_and_end_date(start_date, end_date, MAX_DATE_RANGE_DAYS)
        self.account = account
        self.form_converter = form_converter
        self.last_domain = last_domain
        self.last_time = last_time
        self.last_id = last_id

    def execute(self, limit=None):
        domains = self.account.get_domains()

        it = run_query_over_domains(
            MobileFormSubmissionsQueryFactory(),
            domains,
            limit=limit,
            last_domain=self.last_domain,
            start_date=self.start_date,
            end_date=self.end_date,
            last_time=self.last_time,
            last_id=self.last_id,
        )

        return (self.form_converter.convert(form) for form in it)

    def get_query_params(self, fetched_object):
        return self.form_converter.get_query_params(fetched_object)


def resolve_start_and_end_date(start_date, end_date, maximum_date_range):
    '''
    Provide start and end date values if not supplied.
    '''
    if not end_date:
        end_date = datetime.now(timezone.utc)

    if not start_date:
        start_date = end_date - timedelta(days=30)

    if end_date - start_date > timedelta(days=maximum_date_range):
        raise TooMuchRequestedDataError(
            _('Date ranges with more than {} days are not supported').format(maximum_date_range)
        )

    return start_date, end_date


class EnterpriseDataConverter(ABC):
    @abstractmethod
    def convert(self, data):
        '''
        Converts the provided `data` into a different format.
        '''
        pass

    @classmethod
    @abstractmethod
    def get_query_params(cls, fetched_object):
        '''
        Takes a fetched, converted object and returns the values from this object that will be necessary
        to continue where this query left off.
        '''
        pass

    @classmethod
    @abstractmethod
    def get_kwargs_from_map(cls, map):
        '''
        Takes a map-like object from a continuation request (generally GET/POST) and extracts
        the parameters necessary for initializing an `IterableEnterpriseFormQuery`.
        '''
        pass


class EnterpriseFormReportConverter(EnterpriseDataConverter):
    def __init__(self):
        self.app_lookup = AppIdToNameResolver()

    def convert(self, form):
        domain = form['domain']
        submitted_date = datetime.strptime(form['received_on'][:19], '%Y-%m-%dT%H:%M:%S')
        inserted_at = datetime.strptime(form['inserted_at'][:19], '%Y-%m-%dT%H:%M:%S')

        return {
            'form_id': form['form']['meta']['instanceID'],
            'form_name': form['form']['@name'] or _('Unnamed'),
            'submitted': submitted_date,
            'inserted_at': inserted_at,
            'app_name': self.app_lookup.resolve_app_id_to_name(domain, form['app_id']) or _('App not found'),
            'username': form['form']['meta']['username'],
            'domain': domain
        }

    @classmethod
    def get_query_params(cls, fetched_object):
        return {
            'domain': fetched_object['domain'],
            'inserted_at': fetched_object['inserted_at'],
            'id': fetched_object['form_id']
        }

    @classmethod
    def get_kwargs_from_map(cls, map):
        last_domain = map.get('domain', None)
        last_time = map.get('inserted_at', None)
        if last_time:
            last_time = datetime.fromisoformat(last_time).astimezone(timezone.utc)
        last_id = map.get('id', None)
        return {
            'last_domain': last_domain,
            'last_time': last_time,
            'last_id': last_id
        }

    @classmethod
    def is_initial_query(cls, map):
        last_domain = map.get('domain', None)
        last_time = map.get('inserted_at', None)
        last_id = map.get('id', None)

        return not (last_domain or last_time or last_id)


class AppIdToNameResolver:
    def __init__(self):
        self.domain_lookup_tables = {}

    def resolve_app_id_to_name(self, domain, app_id):
        if 'domain' not in self.domain_lookup_tables:
            domain_apps = get_brief_apps_in_domain(domain)
            self.domain_lookup_tables[domain] = {a.id: a.name for a in domain_apps}

        return self.domain_lookup_tables[domain].get(app_id, None)


def run_query_over_domains(query_factory, domains, limit=None, last_domain=None, **kwargs):
    iterators = []
    if last_domain:
        remaining_domains = dropwhile(lambda d: d != last_domain, domains)
        in_progress_domain = next(remaining_domains)
        iterators.append(run_query_over_domain(query_factory, in_progress_domain, limit=limit, **kwargs))
    else:
        remaining_domains = domains

    fresh_domain_query_args = query_factory.get_next_query_args(kwargs, last_hit=None)
    for domain in remaining_domains:
        iterators.append(run_query_over_domain(query_factory, domain, limit=limit, **fresh_domain_query_args))

    yield from islice(chain.from_iterable(iterators), limit)


def run_query_over_domain(query_factory, domain, limit=None, **kwargs):
    remaining = limit

    next_query_args = kwargs

    while True:
        query = query_factory.get_query(domain, limit=limit, **next_query_args)
        results = query.run()
        for hit in results.hits:
            last_hit = hit
            yield last_hit

        num_fetched = len(results.hits)

        if num_fetched >= results.total or (remaining and num_fetched >= remaining):
            break
        else:
            if remaining:
                remaining -= num_fetched

            next_query_args = query_factory.get_next_query_args(next_query_args, last_hit)


class ReportQueryFactoryInterface(ABC):
    '''
    A generic interface for any report queries.
    '''
    @abstractmethod
    def get_query(self, **kwargs):
        '''
        Returns an ElasticSearch query, configured by `**kwargs`
        '''
        raise NotImplementedError()

    @abstractmethod
    def get_next_query_args(self, previous_args, last_hit):
        '''
        Modifies the `previous_args` dictionary with information from `last_hit` to create
        a new set of kwargs suitable to pass back to `get_query` to retrieve results beyond `last_hit`
        '''
        raise NotImplementedError()


class MobileFormSubmissionsQueryFactory(ReportQueryFactoryInterface):
    def get_query(self, domain, start_date, end_date, last_time=None, last_id=None, limit=None):
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

        if last_time and last_id:
            # The results are first sorted by 'inserted_at', so if the previous query wasn't
            # the only form  submitted for its timestamp, return the others with a greater doc_id
            submitted_same_time_as_previous_result = filters.AND(
                filters.term('inserted_at', es_format_datetime(last_time)),
                filters.range_filter('doc_id', gt=last_id)
            ),
            submitted_prior_to_previous_result = filters.date_range('inserted_at', lt=last_time)

            query = query.filter(filters.OR(
                submitted_same_time_as_previous_result,
                submitted_prior_to_previous_result
            ))

        return query

    def get_next_query_args(self, previous_args, last_hit):
        if last_hit:
            return previous_args | {
                'last_time': last_hit['inserted_at'],
                'last_id': last_hit['doc_id']
            }
        else:
            new_args = previous_args.copy()
            new_args.pop('last_time', None)
            new_args.pop('last_id', None)
            return new_args
