from django.utils.html import format_html
from django.utils.translation import gettext as _

from corehq.motech.repeaters.const import RECORD_QUEUED_STATES, State
from corehq.util.timezones.conversions import ServerTime

MISSING_VALUE = '---'


class RepeatRecordDisplay:
    def __init__(
            self,
            record,
            timezone,
            date_format="%Y-%m-%d %H:%M",
            process_repeaters_enabled=False,
    ):
        self.record = record
        self.timezone = timezone
        self.date_format = date_format
        self.process_repeaters_enabled = process_repeaters_enabled

    @property
    def record_id(self):
        return self.record.id

    @property
    def last_checked(self):
        return self._format_date(self.record.last_checked)

    @property
    def next_check(self):
        if self.record.state not in RECORD_QUEUED_STATES:
            return '---'
        if self.record.repeater.is_paused:
            return _('Paused')
        if self.process_repeaters_enabled:
            next_check_ = self.record.repeater.next_attempt_at
        else:
            next_check_ = self.record.next_check
        return self._format_date(next_check_)

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
        label_cls, label_text = _get_state_tuple(self.record)
        return format_html(f'<span class="label label-{label_cls}">{label_text}</span>')

    def _format_date(self, date):
        if not date:
            return '---'
        return ServerTime(date).user_time(self.timezone).done().strftime(self.date_format)


def _get_state_tuple(record):
    state_map = {
        State.Success: ('success', _('Success')),
        State.Pending: ('warning', _('Pending')),
        State.Cancelled: ('danger', _('Cancelled')),
        State.Fail: ('danger', _('Failed')),
        State.Empty: ('success', _('Empty')),
        State.InvalidPayload: ('danger', _('Invalid payload')),
    }
    return state_map.get(record.state, ('', ''))
