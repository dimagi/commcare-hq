from __future__ import absolute_import
from __future__ import unicode_literals

import six

from collections import defaultdict
from django.contrib import messages
from django.db import transaction
from django.utils.translation import ugettext as _

from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.sms.util import get_language_list
from corehq.messaging.scheduling.exceptions import RuleUpdateError
from corehq.messaging.scheduling.forms import ScheduleForm
from corehq.messaging.scheduling.models.alert_schedule import AlertSchedule
from corehq.messaging.scheduling.models.content import SMSContent
from corehq.messaging.scheduling.models.timed_schedule import TimedSchedule
from corehq.messaging.tasks import initiate_messaging_rule_run


def get_conditional_alerts_queryset_by_domain(domain, query_string=''):
    query = (
        AutomaticUpdateRule
        .objects
        .filter(domain=domain, workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING, deleted=False)
    )
    if query_string:
        query = query.filter(name__icontains=query_string)
    query = query.order_by('case_type', 'name', 'id')
    return query


def get_conditional_alert_headers(domain):
    common_headers = ['id', 'name']
    langs = get_language_list(domain)
    return ((TranslatedConditionalAlertUploader.sheet_name,
             common_headers + ['message_' + lang for lang in langs]),
            (UntranslatedConditionalAlertUploader.sheet_name,
             common_headers + ['message']))


def get_conditional_alert_rows(domain):
    translated_rows = []
    untranslated_rows = []

    langs = get_language_list(domain)
    for rule in get_conditional_alerts_queryset_by_domain(domain):
        schedule = rule.get_messaging_rule_schedule()
        events = schedule.memoized_events
        send_frequency = ScheduleForm.get_send_frequency_by_ui_type(schedule.ui_type)

        # Custom schedules may have multiple events each with different content
        # Non-custom schedules may have multiple events (e.g., daily schedule sent MWF) but each
        # event will have identical content, so only include the first one
        if send_frequency not in (ScheduleForm.SEND_CUSTOM_DAILY, ScheduleForm.SEND_CUSTOM_IMMEDIATE):
            events = [events[0]]

        for event in events:
            if not isinstance(event.content, SMSContent):
                continue
            message = event.content.message
            common_columns = [rule.pk, rule.name]
            if '*' in message or len(message) == 0:
                untranslated_rows.append(common_columns + [message.get('*', '')])
            else:
                translated_rows.append(common_columns + [message.get(lang, '') for lang in langs])

    return (translated_rows, untranslated_rows)


def upload_conditional_alert_workbook(domain, workbook):
    translated_uploader = TranslatedConditionalAlertUploader(domain)
    untranslated_uploader = UntranslatedConditionalAlertUploader(domain)
    return translated_uploader.upload(workbook) + untranslated_uploader.upload(workbook)


class ConditionalAlertUploader(object):
    sheet_name = None

    def __init__(self, domain):
        super(ConditionalAlertUploader, self).__init__()
        self.domain = domain
        self.langs = get_language_list(domain)
        self.msgs = []

    def get_worksheet_errors(self, worksheet):
        if 'id' not in worksheet.headers:
            return [(messages.error, _("The '{sheet_name}' sheet is missing an id column. "
                                       "This sheet has been skipped.".format(sheet_name=self.sheet_name)))]

        return []

    def upload(self, workbook):
        self.msgs = []
        success_count = 0
        worksheet = workbook.get_worksheet(title=self.sheet_name)

        errors = self.get_worksheet_errors(worksheet)
        if errors:
            return errors

        # Most rules are represented by a single row, but rules with custom schedules have one row per event.
        # Read through the worksheet, grouping rows by rule id and caching rule definitions.
        condensed_rows = defaultdict(list)
        rules_by_id = {}

        for index, row in enumerate(worksheet, start=2):    # one-indexed, plus header row
            if not row.get('id', None):
                self.msgs.append((messages.error, _("Row {index} in '{sheet_name}' sheet is missing "
                                  "an id.").format(index=index, sheet_name=self.sheet_name)))
                continue

            if row['id'] in condensed_rows:
                # This is the 2nd (or 3rd, 4th, ...) row for a rule we've already seen
                condensed_rows[row['id']].append(row)
                continue

            rule = getattr(rules_by_id, six.text_type(row['id']), None)
            try:
                rule = AutomaticUpdateRule.objects.get(
                    pk=row['id'],
                    domain=self.domain,
                    workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
                    deleted=False,
                )
            except AutomaticUpdateRule.DoesNotExist:
                self.msgs.append((messages.error,
                                 _("""Could not find rule for row {index} in '{sheet_name}' sheet, """
                                   """with id {id}""").format(index=index,
                                                              id=row['id'],
                                                              sheet_name=self.sheet_name)))
                continue

            if rule.locked_for_editing:
                self.msgs.append((messages.error, _("Row {index} in '{sheet_name}' sheet, with rule id {id}, "
                                  "is currently processing and cannot be updated.").format(index=index,
                                    id=row['id'], sheet_name=self.sheet_name)))
                continue

            if not isinstance(rule.get_messaging_rule_schedule().memoized_events[0].content, SMSContent):
                self.msgs.append((messages.error, _("Row {index} in '{sheet_name}' sheet, with rule id {id}, "
                                  "does not use SMS content.").format(index=index, id=row['id'],
                                                                      sheet_name=self.sheet_name)))
                continue

            rules_by_id[row['id']] = rule
            condensed_rows[row['id']].append(row)

        # Update the condensed set of rules
        for rule_id, rows in condensed_rows.items():
            rule = rules_by_id[rule_id]
            schedule = rule.get_messaging_rule_schedule()
            send_frequency = ScheduleForm.get_send_frequency_by_ui_type(schedule.ui_type)
            is_custom = False

            if send_frequency in (ScheduleForm.SEND_CUSTOM_DAILY, ScheduleForm.SEND_CUSTOM_IMMEDIATE):
                is_custom = True

                # Check that user provided one row for each event in the custom schedule
                expected = len(rule.get_messaging_rule_schedule().memoized_events)
                actual = len(rows)
                if expected != actual:
                    self.msgs.append((messages.error, _("Could not update rule with id {id} in '{sheet_name}' "
                                                        "sheet: expected {expected} row(s) but found "
                                                        "{actual}.").format(id=rule.id, sheet_name=self.sheet_name,
                                                                            expected=expected, actual=actual)))
                    continue

            with transaction.atomic():
                try:
                    dirty = self.update_rule(rule, rows, is_custom=is_custom)
                except RuleUpdateError as e:
                    self.msgs.append((messages.error, _("Error updating rule with id {id} in '{sheet_name}' "
                                      "sheet: {detail}").format(id=rule.id, sheet_name=self.sheet_name,
                                                                detail=six.text_type(e))))
                    continue

                if dirty:
                    rule.save()
                    initiate_messaging_rule_run(self.domain, rule.pk)
                    success_count += 1

        self.msgs.append((messages.success, _("Updated {count} rule(s) in '{sheet_name}' sheet").format(
            count=success_count, sheet_name=self.sheet_name)))

        return self.msgs

    def update_rule(self, rule, rows):
        if len(set([r['name'] for r in rows])) != 1:
            raise RuleUpdateError(_("Rule name must be the same in all rows"))

        row = rows[0]
        dirty = False
        if 'name' in row and rule.name != row['name']:
            dirty = True
            rule.name = row['name']

        return dirty

    def update_rule_messages(self, rule, messages):
        schedule = rule.get_messaging_rule_schedule()
        send_frequency = ScheduleForm.get_send_frequency_by_ui_type(schedule.ui_type)
        {
            ScheduleForm.SEND_IMMEDIATELY: self.save_immediate_schedule,
            ScheduleForm.SEND_DAILY: self.save_daily_schedule,
            ScheduleForm.SEND_WEEKLY: self.save_weekly_schedule,
            ScheduleForm.SEND_MONTHLY: self.save_monthly_schedule,
            ScheduleForm.SEND_CUSTOM_IMMEDIATE: self.save_custom_immediate_schedule,
            ScheduleForm.SEND_CUSTOM_DAILY: self.save_custom_daily_schedule,
        }[send_frequency](schedule, messages)

    def save_immediate_schedule(self, schedule, messages):
        AlertSchedule.assert_is(schedule)
        assert(len(messages) == 1)

        schedule.set_simple_alert(SMSContent(message=messages[0]),
                                  extra_options=schedule.get_extra_scheduling_options())

    def save_daily_schedule(self, schedule, messages):
        TimedSchedule.assert_is(schedule)
        assert(len(messages) == 1)

        schedule.set_simple_daily_schedule(
            schedule.memoized_events[0],
            SMSContent(message=messages[0]),
            total_iterations=schedule.total_iterations,
            start_offset=schedule.start_offset,
            extra_options=schedule.get_extra_scheduling_options(),
            repeat_every=schedule.repeat_every,
        )

    def save_weekly_schedule(self, schedule, messages):
        TimedSchedule.assert_is(schedule)
        assert(len(messages) == 1)

        schedule.set_simple_weekly_schedule(
            schedule.memoized_events[0],
            SMSContent(message=messages[0]),
            [e.day for e in schedule.memoized_events],
            schedule.start_day_of_week,
            total_iterations=schedule.total_iterations,
            extra_options=schedule.get_extra_scheduling_options(),
            repeat_every=schedule.repeat_every,
        )

    def save_monthly_schedule(self, schedule, messages):
        TimedSchedule.assert_is(schedule)
        assert(len(messages) == 1)

        # Negative numbers are used for monthly schedules.
        # See comment on TimedSchedule.repeat_every
        repeat_every = schedule.repeat_every * -1

        schedule.set_simple_monthly_schedule(
            schedule.memoized_events[0],
            [e.day for e in schedule.memoized_events],
            SMSContent(message=messages[0]),
            total_iterations=schedule.total_iterations,
            extra_options=schedule.get_extra_scheduling_options(),
            repeat_every=repeat_every,
        )

    def save_custom_immediate_schedule(self, schedule, messages):
        AlertSchedule.assert_is(schedule)
        assert(len(messages) == len(schedule.memoized_events))

        event_and_content_objects = zip(schedule.memoized_events, [SMSContent(message=m) for m in messages])
        schedule.set_custom_alert(event_and_content_objects, extra_options=schedule.get_extra_scheduling_options())

    def save_custom_daily_schedule(self, schedule, messages):
        TimedSchedule.assert_is(schedule)
        assert(len(messages) == len(schedule.memoized_events))

        event_and_content_objects = zip(schedule.memoized_events, [SMSContent(message=m) for m in messages])
        schedule.set_custom_daily_schedule(
            event_and_content_objects,
            total_iterations=schedule.total_iterations,
            start_offset=schedule.start_offset,
            extra_options=schedule.get_extra_scheduling_options(),
            repeat_every=schedule.repeat_every,
        )


class TranslatedConditionalAlertUploader(ConditionalAlertUploader):
    sheet_name = 'translated'

    def update_rule(self, rule, rows, is_custom=False):
        dirty = super(TranslatedConditionalAlertUploader, self).update_rule(rule, rows)

        if is_custom:
            events_and_rows = zip(rule.get_messaging_rule_schedule().memoized_events, rows)
        else:
            events_and_rows = [(rule.get_messaging_rule_schedule().memoized_events[0], rows[0])]

        message_dirty = False
        new_messages = []
        for event, row in events_and_rows:
            new_message = event.content.message
            new_message.pop('*', None)
            for lang in self.langs:
                key = 'message_' + lang
                if key in row and new_message.get(lang, '') != row[key]:
                    new_message.update({lang: row[key]})
                    message_dirty = True
            new_messages.append(new_message)

        if message_dirty:
            missing = [lang for message in new_messages for lang, value in message.items() if not message[lang]]
            if missing:
                raise RuleUpdateError(_("Missing content for {langs}").format(langs=", ".join(missing)))
            self.update_rule_messages(rule, new_messages)

        return dirty or message_dirty


class UntranslatedConditionalAlertUploader(ConditionalAlertUploader):
    sheet_name = 'not translated'

    def update_rule(self, rule, rows, is_custom=False):
        dirty = super(UntranslatedConditionalAlertUploader, self).update_rule(rule, rows)
        if not any(['message' in row for row in rows]):
            return dirty

        if is_custom:
            events_and_messages = zip(rule.get_messaging_rule_schedule().memoized_events,
                                      [row['message'] for row in rows])
        else:
            events_and_messages = [(rule.get_messaging_rule_schedule().memoized_events[0],
                                    rows[0]['message'])]

        new_messages = []
        for event, message in events_and_messages:
            if event.content.message.get('*', '') != message:
                dirty = True
                if not message:
                    raise RuleUpdateError(_("Missing content"))

            new_messages.append({'*': message})

        if dirty:
            self.update_rule_messages(rule, new_messages)

        return dirty
