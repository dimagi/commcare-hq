from abc import ABCMeta, abstractmethod

import itertools
import six


class BaseIDProvider(six.with_metaclass(ABCMeta)):
    @abstractmethod
    def get_doc_ids(self, domain):
        raise NotImplementedError


class LocationIDProvider(BaseIDProvider):
    def get_doc_ids(self, domain):
        from corehq.apps.locations.models import SQLLocation
        return SQLLocation.objects.filter(domain=domain).location_ids()


class AppIdProvier(BaseIDProvider):
    def get_doc_ids(self, domain):
        from corehq.apps.app_manager.dbaccessors import get_app_ids_in_domain
        from corehq.apps.app_manager.dbaccessors import get_built_app_ids
        app_ids = get_app_ids_in_domain(domain)
        build_apps_ids = get_built_app_ids(domain)
        return itertools.chain(app_ids, build_apps_ids)
