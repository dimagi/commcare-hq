from custom.ilsgateway.tanzania.reminders.reminder import Reminder

from custom.ilsgateway.models import SupplyPointStatusTypes, SupplyPointStatus
from custom.ilsgateway.tanzania.reminders import REMINDER_SUPERVISION


class SupervisionReminder(Reminder):

    def get_message(self):
        return REMINDER_SUPERVISION

    def get_status_type(self):
        return SupplyPointStatusTypes.SUPERVISION_FACILITY

    def location_filter(self, sql_location):
        return not SupplyPointStatus.objects.filter(
            location_id=sql_location.location_id,
            status_type=SupplyPointStatusTypes.SUPERVISION_FACILITY,
            status_date__gte=self.date
        ).exists()
