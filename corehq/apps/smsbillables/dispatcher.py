from django.utils.decorators import method_decorator

from corehq.apps.domain.decorators import require_superuser
from corehq.apps.reports.dispatcher import ReportDispatcher


@method_decorator(require_superuser, name='dispatch')
class SMSAdminInterfaceDispatcher(ReportDispatcher):
    prefix = 'sms_admin_interface'
    map_name = "SMS_ADMIN_INTERFACES"
