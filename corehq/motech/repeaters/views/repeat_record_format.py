from django.template.loader import render_to_string
from django.utils.html import format_html
from django.utils.translation import ugettext as _

from corehq.motech.repeaters.const import (
    RECORD_CANCELLED_STATE,
    RECORD_FAILURE_STATE,
    RECORD_PENDING_STATE,
    RECORD_SUCCESS_STATE,
)
from corehq.util.timezones.conversions import ServerTime


class SimpleFormat:
    def __init__(self, timezone, date_format="%Y-%m-%d %H:%M"):
        self.timezone = timezone
        self.date_format = date_format

    def format_record(self, record):
        url = record.repeater.get_url(record) if record.repeater else _('Unable to generate url for record')
        return {
            'id': record.record_id,
            'last_checked': self._format_date(record.last_checked),
            'next_attempt_at': self._format_date(record.next_attempt_at),
            'url': url,
            'state': format_html('<span class="label label-{}">{}</span>', *_get_state(record)),
            'attempts': render_to_string('repeaters/partials/attempt_history.html', {'record': record}),
        }

    def _format_date(self, date):
        if not date:
            return '---'
        return ServerTime(date).user_time(self.timezone).done().strftime(self.date_format)


def _get_state(record):
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
    else:
        label_cls = ''
        label_text = ''

    return label_cls, label_text
