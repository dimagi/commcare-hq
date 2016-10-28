from abc import ABCMeta, abstractmethod

import six
from django.db.models import Q


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
