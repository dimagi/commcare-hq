from __future__ import absolute_import
from __future__ import unicode_literals
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
        self.domain = self.model_class = self.db_alias = None

    def prepare(self, domain, model_class, db_alias):
        self.domain = domain
        self.model_class = model_class
        self.db_alias = db_alias
        return self

    def _base_queryset(self):
        assert self.domain and self.model_class and self.db_alias, "Unprepared IteratorBuilder"
        objects = self.model_class._default_manager
        return objects.using(self.db_alias).order_by(self.model_class._meta.pk.name)

    def querysets(self):
        return self._base_queryset()

    def iterators(self):
        for queryset in self.querysets():
            yield queryset.iterator()

    def build(self, domain, model_class, db_alias):
        return self.__class__(self.model_label).prepare(domain, model_class, db_alias)


class FilteredModelIteratorBuilder(UnfilteredModelIteratorBuilder):
    def __init__(self, model_label, filter):
        super(FilteredModelIteratorBuilder, self).__init__(model_label)
        self.filter = filter

    def build(self, domain, model_class, db_alias):
        return self.__class__(self.model_label, self.filter).prepare(domain, model_class, db_alias)

    def querysets(self):
        queryset = self._base_queryset()
        filters = self.filter.get_filters(self.domain)
        for filter in filters:
            yield queryset.filter(filter)


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
