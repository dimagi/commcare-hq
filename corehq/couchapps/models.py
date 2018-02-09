from __future__ import absolute_import
from dimagi.ext.jsonobject import (
    JsonObject, IntegerProperty, DateTimeProperty, StringProperty)


class ReportsForm(JsonObject):
    time = DateTimeProperty()
    completion_time = DateTimeProperty()
    start_time = DateTimeProperty()
    duration = IntegerProperty()
    submission_time = DateTimeProperty()
    xmlns = StringProperty()
    app_id = StringProperty()
    user_id = StringProperty()
    username = StringProperty()
