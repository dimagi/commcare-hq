from corehq.apps.commtrack.models import StockState
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import WebUser
from custom.ewsghana.models import EWSExtension
from custom.ewsghana.reminders import STOCKOUT_REPORT
from custom.ewsghana.reminders.web_user_reminder import WebUserReminder
from custom.ewsghana.utils import has_notifications_enabled


class StockoutReminder(WebUserReminder):

    def get_users(self):
        return WebUser.by_domain(self.domain)

    def recipients_filter(self, user):
        return has_notifications_enabled(self.domain, user)

    def _get_stockouts(self, case_id):
        return StockState.objects.filter(
            case_id=case_id, stock_on_hand=0
        ).values_list('sql_product__name', flat=True)

    def get_message(self, recipient):
        web_user = recipient
        try:
            extension = EWSExtension.objects.get(user_id=web_user.get_id, domain=self.domain)
        except EWSExtension.DoesNotExist:
            return

        if not extension.location_id:
            return

        sql_location = SQLLocation.objects.get(location_id=extension.location_id, domain=self.domain)
        products_names = self._get_stockouts(sql_location.supply_point_id)
        if not products_names:
            return

        try:
            last_report_date = StockState.objects.filter(
                case_id=sql_location.supply_point_id
            ).latest('last_modified_date').last_modified_date.strftime('%b %d')
        except StockState.DoesNotExist:
            last_report_date = ''
        return STOCKOUT_REPORT % {
            'name': web_user.full_name,
            'facility': sql_location.name,
            'date': last_report_date,
            'products': ', '.join(products_names)
        }
