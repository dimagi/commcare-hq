from __future__ import absolute_import
from __future__ import unicode_literals

import six
from django.http import Http404
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.domain.views.base import DomainViewMixin
from memoized import memoized
from dimagi.utils.logging import notify_exception


class ApplicationViewMixin(DomainViewMixin):
    """
    Helper for class-based views in app manager
    """

    @property
    @memoized
    def app_id(self):
        return self.args[1] if len(self.args) > 1 else self.kwargs.get('app_id')

    @property
    def app(self):
        return self.get_app(self.app_id)

    @memoized
    def get_app(self, app_id):
        try:
            return get_app(self.domain, app_id)
        except Http404 as e:
            raise e
        except Exception as e:
            notify_exception(self.request, message=six.text_type(e))
        return None
