from __future__ import absolute_import
from __future__ import unicode_literals
from django.http import Http404
from django.views.generic.base import TemplateView
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.domain.views import DomainViewMixin
from memoized import memoized
from dimagi.utils.logging import notify_exception


class ApplicationViewMixin(DomainViewMixin):
    """
    Helper for class-based views in app manager

    Currently only used in hqmedia

    """

    @property
    @memoized
    def app_id(self):
        return self.args[1] if len(self.args) > 1 else self.kwargs.get('app_id')

    @property
    @memoized
    def app(self):
        try:
            # if get_app is mainly used for views,
            # maybe it should be a classmethod of this mixin? todo
            return get_app(self.domain, self.app_id)
        except Http404 as e:
            raise e
        except Exception as e:
            notify_exception(self.request, message=e.message)
        return None


class DynamicTemplateView(TemplateView):

    def get_template_names(self):
        return ['app_manager/ng_partials/%s.html' % self.kwargs['template']]
