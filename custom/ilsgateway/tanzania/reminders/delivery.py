from custom.ilsgateway.models import SupplyPointStatusTypes, DeliveryGroups
from custom.ilsgateway.tanzania.reminders import REMINDER_DELIVERY_FACILITY, REMINDER_DELIVERY_DISTRICT
from custom.ilsgateway.tanzania.reminders.reminder import GroupReminder


class DeliveryReminder(GroupReminder):

    @property
    def current_group(self):
        return DeliveryGroups().current_delivering_group(self.date.month)

    def get_message(self):
        if self.location_type == 'FACILITY':
            return REMINDER_DELIVERY_FACILITY
        elif self.location_type == 'DISTRICT':
            return REMINDER_DELIVERY_DISTRICT

    def get_status_type(self):
        if self.location_type == 'FACILITY':
            return SupplyPointStatusTypes.DELIVERY_FACILITY
        elif self.location_type == 'DISTRICT':
            return SupplyPointStatusTypes.DELIVERY_DISTRICT
