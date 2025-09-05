from django.http import Http404
from django.utils.decorators import method_decorator

from memoized import memoized

from dimagi.utils.logging import notify_exception

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.decorators import require_can_view_apps
from corehq.apps.domain.views.base import DomainViewMixin


class ApplicationViewMixin(DomainViewMixin):
    """
    Helper for class-based views in app manager
    """

    @method_decorator(require_can_view_apps)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

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
            notify_exception(self.request, message=str(e))
        return None
