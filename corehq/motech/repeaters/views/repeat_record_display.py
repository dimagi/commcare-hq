from django.utils.html import format_html
from django.utils.translation import gettext as _

from corehq.motech.repeaters.const import (
    RECORD_CANCELLED_STATE,
    RECORD_FAILURE_STATE,
    RECORD_PENDING_STATE,
    RECORD_SUCCESS_STATE,
    RECORD_EMPTY_STATE,
)
from corehq.util.timezones.conversions import ServerTime

MISSING_VALUE = '---'


class RepeatRecordDisplay:
    def __init__(self, record, timezone, date_format="%Y-%m-%d %H:%M"):
        self.record = record
        self.timezone = timezone
        self.date_format = date_format

    @property
    def record_id(self):
        return self.record.id

    @property
    def last_checked(self):
        return self._format_date(self.record.last_checked)

    @property
    def next_attempt_at(self):
        return self._format_date(self.record.next_attempt_at)

    @property
    def url(self):
        if self.record.repeater:
            return self.record.repeater.get_url(self.record)
        else:
            return _('Unable to generate url for record')

    @property
    def remote_service(self):
        if self.record.repeater:
            return str(self.record.repeater)
        return MISSING_VALUE

    @property
    def state(self):
        return format_html('<span class="label label-{}">{}</span>', *_get_state_tuple(self.record))

    def _format_date(self, date):
        if not date:
            return '---'
        return ServerTime(date).user_time(self.timezone).done().strftime(self.date_format)


def _get_state_tuple(record):
    if record.state == RECORD_SUCCESS_STATE:
        label_cls = 'success'
        label_text = _('Success')
    elif record.state == RECORD_PENDING_STATE:
        label_cls = 'warning'
        label_text = _('Pending')
    elif record.state == RECORD_CANCELLED_STATE:
        label_cls = 'danger'
        label_text = _('Cancelled')
    elif record.state == RECORD_FAILURE_STATE:
        label_cls = 'danger'
        label_text = _('Failed')
    elif record.state == RECORD_EMPTY_STATE:
        label_cls = 'success'
        label_text = _('Empty')
    else:
        label_cls = ''
        label_text = ''

    return label_cls, label_text
