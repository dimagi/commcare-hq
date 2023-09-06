from collections import defaultdict
from copy import copy
from django.contrib import messages
from django.db import transaction
from django.utils.translation import gettext as _

from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.sms.util import get_language_list
from corehq.messaging.scheduling.exceptions import RuleUpdateError
from corehq.messaging.scheduling.forms import ScheduleForm
from corehq.messaging.scheduling.models.alert_schedule import AlertSchedule
from corehq.messaging.scheduling.models.content import SMSContent
from corehq.messaging.scheduling.models.timed_schedule import TimedSchedule
from corehq.util.workbook_json.excel import WorksheetNotFound


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
        schedule = rule.get_schedule()
        events = schedule.memoized_events
        send_frequency = ScheduleForm.get_send_frequency_by_ui_type(schedule.ui_type)

        # Custom schedules may have multiple events each with different content
        # Non-custom schedules may have multiple events (e.g., daily schedule sent MWF) but each
        # event will have identical content, so only include the first one
        if send_frequency not in (ScheduleForm.SEND_CUSTOM_DAILY, ScheduleForm.SEND_CUSTOM_IMMEDIATE):
            events = [events[0]]

        for event in events:
            common_columns = [rule.pk, rule.name]
            if UntranslatedConditionalAlertUploader.event_is_relevant(event):
                untranslated_rows.append(common_columns + [event.content.message.get('*', '')])
            elif TranslatedConditionalAlertUploader.event_is_relevant(event):
                translated_rows.append(common_columns + [event.content.message.get(lang, '') for lang in langs])

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

    @classmethod
    def event_is_relevant(cls, event):
        """
        Whether the event belongs on the given sheet.
        During download, this filters events onto the correct sheet.
        During upload, depending on the circumstances, events may be allowed to change sheets.
        """
        return isinstance(event.content, SMSContent)

    def get_worksheet_errors(self, worksheet):
        if 'id' not in worksheet.headers:
            return [(messages.error, _("The '{sheet_name}' sheet is missing an id column. "
                                       "This sheet has been skipped.".format(sheet_name=self.sheet_name)))]

        return []

    def upload(self, workbook):
        self.msgs = []
        success_count = 0

        try:
            worksheet = workbook.get_worksheet(title=self.sheet_name)
        except WorksheetNotFound:
            return [(messages.error, _("This file is missing the '{sheet_name}' sheet. Please add this sheet "
                                       "and upload again.".format(sheet_name=self.sheet_name)))]

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

            if not isinstance(rule.get_schedule().memoized_events[0].content, SMSContent):
                self.msgs.append((messages.error, _("Row {index} in '{sheet_name}' sheet, with rule id {id}, "
                                  "does not use SMS content.").format(index=index, id=row['id'],
                                                                      sheet_name=self.sheet_name)))
                continue

            rules_by_id[row['id']] = rule
            condensed_rows[row['id']].append(row)

        # Update the condensed set of rules
        for rule_id, rows in condensed_rows.items():
            rule = rules_by_id[rule_id]
            schedule = rule.get_schedule()
            send_frequency = ScheduleForm.get_send_frequency_by_ui_type(schedule.ui_type)

            if send_frequency in (ScheduleForm.SEND_CUSTOM_DAILY, ScheduleForm.SEND_CUSTOM_IMMEDIATE):
                # Check that user provided one row for each event in the custom schedule
                all_events = rule.get_schedule().memoized_events
                expected = len([e for e in all_events if self.event_is_relevant(e)])
                actual = len(rows)
                if expected != actual and actual != len(all_events):
                    self.msgs.append((messages.error, _("Could not update rule with id {id} in '{sheet_name}' "
                                                        "sheet: expected {expected} row(s) but found "
                                                        "{actual}.").format(id=rule.id, sheet_name=self.sheet_name,
                                                                            expected=expected, actual=actual)))
                    continue

            with transaction.atomic():
                try:
                    dirty = self.update_rule(rule, rows)
                except RuleUpdateError as e:
                    self.msgs.append((messages.error, _("Error updating rule with id {id} in '{sheet_name}' "
                                      "sheet: {detail}").format(id=rule.id, sheet_name=self.sheet_name,
                                                                detail=str(e))))
                    continue

                if dirty:
                    rule.save()
                    success_count += 1

        self.msgs.append((messages.success, _("Updated {count} rule(s) in '{sheet_name}' sheet").format(
            count=success_count, sheet_name=self.sheet_name)))

        return self.msgs

    def update_rule(self, rule, rows):
        name_dirty = self.update_rule_name(rule, rows)
        message_dirty = self.save_rule_messages(rule, rows)
        return name_dirty or message_dirty

    def update_rule_name(self, rule, rows):
        if len(set([r['name'] for r in rows])) != 1:
            raise RuleUpdateError(_("Rule name must be the same in all rows"))

        row = rows[0]
        if 'name' in row and rule.name != row['name']:
            rule.name = row['name']
            return True
        return False

    def save_rule_messages(self, rule, rows):
        schedule = rule.get_schedule()
        send_frequency = ScheduleForm.get_send_frequency_by_ui_type(schedule.ui_type)

        # Iterate over rule's events
        if send_frequency not in (ScheduleForm.SEND_CUSTOM_DAILY, ScheduleForm.SEND_CUSTOM_IMMEDIATE):
            # For standard schedules, the rule may have multiple events (e.g., a daily rule run Mon and Tues
            # will have 2 events), but all events will have the same message, so we only need to look at the
            # first event. Since there's only one message, the user is free to move it between sheets.
            events = [rule.get_schedule().memoized_events[0]]
            allow_sheet_swap = True
        else:
            # For custom schedules, each event has its own message, so we need to look at all of them, and they may
            # be a mix of translated and untranslated.
            # If all messages are on one sheet: The user may update any or all and may move ALL of them to the
            #   other sheet. We assume that the order of rows is the same as the rule's order of events.
            # If messages are split between sheets: The user may only make updates on one sheet (once the first
            #   sheet is updated, the rule will begin processing, so the second sheet's updates will fail). Again,
            #   we assume the order of rows matches the order of events (with the other sheet's rows interleaved).
            #   The user may not move messages between sheets, since we can't match events to messages.
            events = rule.get_schedule().memoized_events
            allow_sheet_swap = len(rows) == len(events)

        message_dirty = False
        new_messages = []
        row_index = 0
        for event in events:
            old_message = event.content.message
            new_message = copy(old_message)
            if self.event_is_relevant(event) or allow_sheet_swap:
                new_message = self.update_message(new_message, rows[row_index])
                message_dirty = message_dirty or old_message != new_message
                row_index += 1
            new_messages.append(new_message)

        {
            ScheduleForm.SEND_IMMEDIATELY: self._save_immediate_schedule,
            ScheduleForm.SEND_DAILY: self._save_daily_schedule,
            ScheduleForm.SEND_WEEKLY: self._save_weekly_schedule,
            ScheduleForm.SEND_MONTHLY: self._save_monthly_schedule,
            ScheduleForm.SEND_CUSTOM_IMMEDIATE: self._save_custom_immediate_schedule,
            ScheduleForm.SEND_CUSTOM_DAILY: self._save_custom_daily_schedule,
        }[send_frequency](schedule, new_messages)

        return message_dirty

    def update_message(self, message, row):
        """
        Update the given message with values from given row, return updated message.
        """
        raise NotImplementedError()

    def _save_immediate_schedule(self, schedule, messages):
        AlertSchedule.assert_is(schedule)
        assert len(messages) == 1, "Immediate schedule expected 1 message, got %s" % len(messages)

        schedule.set_simple_alert(SMSContent(message=messages[0]),
                                  extra_options=schedule.get_extra_scheduling_options())

    def _save_daily_schedule(self, schedule, messages):
        TimedSchedule.assert_is(schedule)
        assert len(messages) == 1, "Daily schedule expected 1 message, got %s" % len(messages)

        schedule.set_simple_daily_schedule(
            schedule.memoized_events[0],
            SMSContent(message=messages[0]),
            total_iterations=schedule.total_iterations,
            start_offset=schedule.start_offset,
            extra_options=schedule.get_extra_scheduling_options(),
            repeat_every=schedule.repeat_every,
        )

    def _save_weekly_schedule(self, schedule, messages):
        TimedSchedule.assert_is(schedule)
        assert len(messages) == 1, "Weekly schedule expected 1 message, got %s" % len(messages)

        schedule.set_simple_weekly_schedule(
            schedule.memoized_events[0],
            SMSContent(message=messages[0]),
            [e.day for e in schedule.memoized_events],
            schedule.start_day_of_week,
            total_iterations=schedule.total_iterations,
            extra_options=schedule.get_extra_scheduling_options(),
            repeat_every=schedule.repeat_every,
        )

    def _save_monthly_schedule(self, schedule, messages):
        TimedSchedule.assert_is(schedule)
        assert len(messages) == 1, "Monthly schedule expected 1 message, got %s" % len(messages)

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

    def _save_custom_immediate_schedule(self, schedule, messages):
        AlertSchedule.assert_is(schedule)
        assert len(messages) == len(schedule.memoized_events), \
            "Custom schedule expected {} messages, got {}".format(len(messages), len(schedule.memoized_events))

        event_and_content_objects = list(zip(schedule.memoized_events, [SMSContent(message=m) for m in messages]))
        schedule.set_custom_alert(event_and_content_objects, extra_options=schedule.get_extra_scheduling_options())

    def _save_custom_daily_schedule(self, schedule, messages):
        TimedSchedule.assert_is(schedule)
        assert len(messages) == len(schedule.memoized_events), \
            "Custom schedule expected {} messages, got {}".format(len(messages), len(schedule.memoized_events))

        event_and_content_objects = list(zip(schedule.memoized_events, [SMSContent(message=m) for m in messages]))
        schedule.set_custom_daily_schedule(
            event_and_content_objects,
            total_iterations=schedule.total_iterations,
            start_offset=schedule.start_offset,
            extra_options=schedule.get_extra_scheduling_options(),
            repeat_every=schedule.repeat_every,
        )


class TranslatedConditionalAlertUploader(ConditionalAlertUploader):
    sheet_name = 'translated'

    @classmethod
    def event_is_relevant(cls, event):
        if not super(TranslatedConditionalAlertUploader, cls).event_is_relevant(event):
            return False

        message = event.content.message
        return len(message) and '*' not in message

    def update_message(self, message, row):
        message.pop('*', None)
        for lang in self.langs:
            key = 'message_' + lang
            if key in row:
                message[lang] = row[key]
        if not any(message.values()):
            raise RuleUpdateError(_("Missing message"))
        return message


class UntranslatedConditionalAlertUploader(ConditionalAlertUploader):
    sheet_name = 'not translated'

    @classmethod
    def event_is_relevant(cls, event):
        if not super(UntranslatedConditionalAlertUploader, cls).event_is_relevant(event):
            return False

        message = event.content.message
        return (not len(message) or '*' in message)

    def update_message(self, message, row):
        if 'message' in row:
            if not row['message']:
                raise RuleUpdateError(_("Missing message"))
            return {'*': row['message']}
        return message
