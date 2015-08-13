from dimagi.ext.couchdbkit import *


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
