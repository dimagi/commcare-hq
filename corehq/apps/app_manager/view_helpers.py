from corehq.apps.app_manager.models import get_app
from corehq.apps.domain.views import DomainViewMixin
from dimagi.utils.decorators.memoized import memoized


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
        except Exception:
            pass
        return None
