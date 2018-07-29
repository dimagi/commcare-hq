from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.domain.decorators import cls_to_view
from corehq.apps.reports.dispatcher import ReportDispatcher
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions

# this is the permissions setting that makes the most sense now,
# but perhaps there should be a specific edit_indicators permission?
require_edit_indicators = require_permission(Permissions.edit_data)
cls_require_edit_indicators = cls_to_view(additional_decorator=require_edit_indicators)


class IndicatorAdminInterfaceDispatcher(ReportDispatcher):
    prefix = "indicator_admin_interface"
    map_name = "INDICATOR_ADMIN_INTERFACES"

    @cls_require_edit_indicators
    def dispatch(self, request, *args, **kwargs):
        return super(IndicatorAdminInterfaceDispatcher, self).dispatch(request, *args, **kwargs)


