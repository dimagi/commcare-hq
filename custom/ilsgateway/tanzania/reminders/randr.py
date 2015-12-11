from custom.ilsgateway.models import SupplyPointStatusTypes, DeliveryGroups
from custom.ilsgateway.tanzania.reminders import REMINDER_R_AND_R_FACILITY, REMINDER_R_AND_R_DISTRICT
from custom.ilsgateway.tanzania.reminders.reminder import GroupReminder


class RandrReminder(GroupReminder):

    @property
    def current_group(self):
        return DeliveryGroups().current_submitting_group(self.date.month)

    def get_message(self):
        if self.location_type == 'FACILITY':
            return REMINDER_R_AND_R_FACILITY
        elif self.location_type == 'DISTRICT':
            return REMINDER_R_AND_R_DISTRICT

    def get_status_type(self):
        if self.location_type == 'FACILITY':
            return SupplyPointStatusTypes.R_AND_R_FACILITY
        elif self.location_type == 'DISTRICT':
            return SupplyPointStatusTypes.R_AND_R_DISTRICT
