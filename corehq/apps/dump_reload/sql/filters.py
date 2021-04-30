from abc import ABCMeta, abstractmethod

from django.db.models import Q
from corehq.util.queries import queryset_to_iterator

from dimagi.utils.chunked import chunked


class DomainFilter(metaclass=ABCMeta):
    @abstractmethod
    def get_filters(self, domain_name):
        """Return a list of filters. Each filter will be applied to a queryset independently
        of the others."""
        raise NotImplementedError()

    def count(self, domain_name):
        return None


class SimpleFilter(DomainFilter):
    def __init__(self, filter_kwarg):
        self.filter_kwarg = filter_kwarg

    def get_filters(self, domain_name):
        return [Q(**{self.filter_kwarg: domain_name})]


class ManyFilters(DomainFilter):
    """
    Filter by multiple filter kwargs. Filters are ANDed
    """
    def __init__(self, *filter_kwargs):
        assert filter_kwargs, 'Please set one of more filter_kwargs'
        self.filter_kwargs = filter_kwargs

    def get_filters(self, domain_name):
        filter_ = Q(**{self.filter_kwargs[0]: domain_name})
        for filter_kwarg in self.filter_kwargs[1:]:
            filter_ &= Q(**{filter_kwarg: domain_name})
        return [filter_]


class UsernameFilter(DomainFilter):
    def __init__(self, usernames=None):
        self.usernames = usernames

    def count(self, domain_name):
        return len(self.usernames) if self.usernames is not None else None

    def get_filters(self, domain_name):
        """
        :return: A generator of filters each filtering for at most 500 users.
        """
        from corehq.apps.users.dbaccessors import get_all_usernames_by_domain
        if self.usernames:
            usernames = self.usernames
        else:
            usernames = get_all_usernames_by_domain(domain_name)
        for chunk in chunked(usernames, 500):
            filter = Q()
            for username in chunk:
                filter |= Q(username__iexact=username)
            yield filter


class IDFilter(DomainFilter):
    def __init__(self, field, ids, chunksize=1000):
        self.field = field
        self.ids = ids
        self.chunksize = chunksize

    def count(self, domain_name):
        return len(self.get_ids(domain_name))

    def get_ids(self, domain_name):
        return self.ids

    def get_filters(self, domain_name):
        for chunk in chunked(self.get_ids(domain_name), self.chunksize):
            query_kwarg = '{}__in'.format(self.field)
            yield Q(**{query_kwarg: chunk})


class UserIDFilter(IDFilter):
    def __init__(self, user_id_field, include_web_users=True):
        super().__init__(user_id_field, None)
        self.include_web_users = include_web_users

    def get_ids(self, domain_name):
        from corehq.apps.users.dbaccessors import get_all_user_ids_by_domain
        return get_all_user_ids_by_domain(domain_name, include_web_users=self.include_web_users)


class UnfilteredModelIteratorBuilder(object):
    def __init__(self, model_label):
        self.model_label = model_label
        self.domain = self.model_class = self.db_alias = None

    def prepare(self, domain, model_class, db_alias):
        self.domain = domain
        self.model_class = model_class
        self.db_alias = db_alias
        return self

    def _base_queryset(self):
        assert self.domain and self.model_class and self.db_alias, "Unprepared IteratorBuilder"
        objects = self.model_class._default_manager
        return objects.using(self.db_alias)

    def querysets(self):
        yield self._base_queryset()

    def count(self):
        return sum(q.count() for q in self.querysets())

    def iterators(self):
        for queryset in self.querysets():
            yield queryset_to_iterator(queryset, self.model_class, ignore_ordering=True)

    def build(self, domain, model_class, db_alias):
        return self.__class__(self.model_label).prepare(domain, model_class, db_alias)


class FilteredModelIteratorBuilder(UnfilteredModelIteratorBuilder):
    def __init__(self, model_label, filter):
        super(FilteredModelIteratorBuilder, self).__init__(model_label)
        self.filter = filter

    def build(self, domain, model_class, db_alias):
        return self.__class__(self.model_label, self.filter).prepare(domain, model_class, db_alias)

    def count(self):
        count = self.filter.count(self.domain)
        if count is not None:
            return count
        return super(FilteredModelIteratorBuilder, self).count()

    def querysets(self):
        queryset = self._base_queryset()
        filters = self.filter.get_filters(self.domain)
        for filter_ in filters:
            yield queryset.filter(filter_)


class UniqueFilteredModelIteratorBuilder(FilteredModelIteratorBuilder):
    def iterators(self):
        def _unique(iterator):
            seen = set()
            for model in iterator:
                if model.pk not in seen:
                    seen.add(model.pk)
                    yield model

        querysets = self.querysets()
        for querysets in querysets:
            yield _unique(querysets)
