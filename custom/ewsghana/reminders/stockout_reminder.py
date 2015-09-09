from corehq.apps.commtrack.models import StockState
from corehq.apps.users.models import WebUser
from custom.ewsghana.reminders import STOCKOUT_REPORT
from custom.ewsghana.reminders.reminder import Reminder


class StockoutReminder(Reminder):

    def get_users(self):
        return WebUser.by_domain(self.domain)

    def recipients_filter(self, user):
        return user.user_data.get('sms_notifications', False) and user.get_verified_number()

    def _get_stockouts(self, case_id):
        return StockState.objects.filter(
            case_id=case_id, stock_on_hand=0
        ).values_list('sql_product__name', flat=True)

    def get_message(self, recipient):
        web_user = recipient.owner
        sql_location = web_user.get_sql_location(self.domain)
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
