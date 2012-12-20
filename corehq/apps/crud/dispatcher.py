from corehq.apps.domain.decorators import cls_require_superusers
from corehq.apps.reports.dispatcher import ReportDispatcher

class BaseCRUDAdminInterfaceDispatcher(ReportDispatcher):
    """
        All CRUD Admin Interfaces should require superuser level access to see.
    """
    @cls_require_superusers
    def dispatch(self, request, *args, **kwargs):
        return super(BaseCRUDAdminInterfaceDispatcher, self).dispatch(request, *args, **kwargs)