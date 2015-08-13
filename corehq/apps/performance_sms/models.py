from corehq.apps.groups.models import Group
from corehq.apps.sms.api import send_sms_to_verified_number
from dimagi.ext.couchdbkit import *
from dimagi.utils.decorators.memoized import memoized


DAILY = "daily"
WEEKLY = "weekly"
MONTHLY = "monthly"


class ScheduleConfiguration(DocumentSchema):
    interval = StringProperty(choices=[DAILY, WEEKLY, MONTHLY])
    hour = IntegerProperty(default=8)
    day_of_week = IntegerProperty(default=1)  # same as cron, 1 = Monday (0 and 7 = Sunday)
    day_of_month = IntegerProperty(default=1)


class TemplateVariable(DocumentSchema):

    type = StringProperty(required=True, choices=['form'])  # todo: can extend to cases
    time_range = StringProperty()
    # Either the case type or the form xmlns that this template variable is based on.
    source_id = StringProperty()
    # The app that the form belongs to - not currently used, but could be used in the future to prevent
    # duplicate XMLNSes in the same project
    app_id = StringProperty()


class PerformanceConfiguration(Document):
    domain = StringProperty(required=True)
    recipient_id = StringProperty(required=True)  # an ID of a Group
    schedule = SchemaProperty(ScheduleConfiguration)
    template_variables = SchemaListProperty(TemplateVariable)
    template = StringProperty(required=True)

    @property
    @memoized
    def group(self):
        group = Group.get(self.recipient_id)
        assert group.domain == self.domain
        return group

    def fire_messages(self):
        for user in self.group.users:
            recipient_number = user.get_verified_number()
            message_text = self.get_message_text(user)
            send_sms_to_verified_number(recipient_number, message_text)

    def get_phone_numbers(self):
        for user in self.group.users:
            yield user.get_verified_number()

    def get_message_text(self):
        raise NotImplementedError("Todo")
