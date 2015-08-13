from corehq.apps.sms.api import send_sms_to_verified_number
from dimagi.ext.couchdbkit import *
from . import dbaccessors


class ScheduleConfiguration(DocumentSchema):
    interval = StringProperty(choices=["daily", "weekly", "monthly"])
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

    def fire_messages(self):
        recipient_phone_numbers = self.get_phone_numbers()
        message_text = self.get_message_text()
        for number in recipient_phone_numbers:
            send_sms_to_verified_number(number, message_text)

    def get_phone_numbers(self):
        recipient_group = Group.get(recipient_id)
        assert recipient_group.domain == self.domain
        for user in recipient_group.users:
            yield user.get_verified_number()

    def get_message_text(self):
        raise NotImplementedError("Todo")

    @classmethod
    def get_message_configs_at_this_hour(cls):
        as_of = as_of or datetime.utcnow()

        def _keys(period, as_of):
            if period == 'daily':
                yield {
                    'key': [period, as_of.hour],
                }
            elif period == 'weekly':
                yield {
                    'key': [period, 1, as_of.weekday()],
                }
            else:
                # monthly
                yield {
                    'key': [period, 1, 1, as_of.day]
                }

        for period in ('daily', 'weekly', 'monthly'):
            for keys in _keys(period, as_of):
                for config in dbaccessors.by_interval(keys).all():
                    yield config
