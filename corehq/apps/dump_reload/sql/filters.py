from abc import ABCMeta, abstractmethod

import six
from django.db.models import Q

from dimagi.utils.chunked import chunked


class DomainFilter(six.with_metaclass(ABCMeta)):
    @abstractmethod
    def get_filters(self, domain_name):
        """Return a list of filters. Each filter will be applied to a queryset independently
        of the others."""
        raise NotImplementedError()


class SimpleFilter(DomainFilter):
    def __init__(self, filter_kwarg):
        self.filter_kwarg = filter_kwarg

    def get_filters(self, domain_name):
        return [Q(**{self.filter_kwarg: domain_name})]


class UsernameFilter(DomainFilter):
    def get_filters(self, domain_name):
        """
        :return: A generator of filters each filtering for at most 500 users.
        """
        from corehq.apps.users.dbaccessors.all_commcare_users import get_all_usernames_by_domain
        usernames = get_all_usernames_by_domain(domain_name)
        for chunk in chunked(usernames, 500):
            filter = Q()
            for username in chunk:
                filter |= Q(username__iexact=username)
            yield filter


class UserIDFilter(DomainFilter):
    def __init__(self, user_id_field, include_web_users=True):
        self.user_id_field = user_id_field
        self.include_web_users = include_web_users

    def get_filters(self, domain_name):
        """
        :return: A generator of filters each filtering for at most 1000 users.
        """
        from corehq.apps.users.dbaccessors.all_commcare_users import get_all_user_ids_by_domain
        user_ids = get_all_user_ids_by_domain(domain_name, include_web_users=self.include_web_users)
        for chunk in chunked(user_ids, 1000):
            query_kwarg = '{}__in'.format(self.user_id_field)
            yield Q(**{query_kwarg: chunk})


class UnfilteredModelIteratorBuilder(object):
    def __init__(self, model_label):
        self.model_label = model_label

    def queryset(self, model_class, db_alias):
        objects = model_class._default_manager
        return objects.using(db_alias).order_by(model_class._meta.pk.name)

    def build(self, domain, model_class, db_alias):
        queryset = self.queryset(model_class, db_alias)
        return [queryset.iterator()]


class FilteredModelIteratorBuilder(UnfilteredModelIteratorBuilder):
    def __init__(self, model_label, filter):
        super(FilteredModelIteratorBuilder, self).__init__(model_label)
        self.filter = filter

    def build(self, domain, model_class, db_alias):
        queryset = self.queryset(model_class, db_alias)
        filters = self.filter.get_filters(domain)
        for filter in filters:
            yield queryset.filter(filter).iterator()


class UniqueFilteredModelIteratorBuilder(FilteredModelIteratorBuilder):
    def build(self, domain, model_class, db_alias):
        def _unique(iterator):
            seen = set()
            for model in iterator:
                if model.pk not in seen:
                    seen.add(model.pk)
                    yield model

        iterators = super(UniqueFilteredModelIteratorBuilder, self).build(domain, model_class, db_alias)
        for iterator in iterators:
            yield _unique(iterator)
