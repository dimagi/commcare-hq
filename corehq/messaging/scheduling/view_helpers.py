from __future__ import absolute_import
from __future__ import unicode_literals

from django.contrib import messages
from django.db import transaction
from django.utils.translation import ugettext as _

from corehq.apps.data_interfaces.models import AutomaticUpdateRule, CreateScheduleInstanceActionDefinition
from corehq.messaging.scheduling.forms import (
    ConditionalAlertCriteriaForm,
    ConditionalAlertScheduleForm,
    ScheduleForm,
)
from corehq.messaging.scheduling.models.abstract import Schedule
from corehq.messaging.scheduling.models.content import SMSContent
from corehq.messaging.scheduling.models.timed_schedule import TimedSchedule
from corehq import toggles


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

def get_conditional_alert_rows(domain, langs):
    translated_rows = []
    untranslated_rows = []

    for rule in get_conditional_alerts_queryset_by_domain(domain):
        if not isinstance(_get_rule_content(rule), SMSContent):
            continue
        message = rule.get_messaging_rule_schedule().memoized_events[0].content.message
        common_columns = [rule.pk, rule.name, rule.case_type]
        if '*' in message or len(message) == 0:
            untranslated_rows.append(common_columns + [message.get('*', '')])
        else:
            translated_rows.append(common_columns + [message.get(lang, '') for lang in langs])

    return (translated_rows, untranslated_rows)


def upload_conditional_alert_workbook(domain, langs, workbook):
    translated_uploader = TranslatedConditionalAlertUploader(domain, langs)
    untranslated_uploader = UntranslatedConditionalAlertUploader(domain, langs)
    return translated_uploader.upload(workbook) + untranslated_uploader.upload(workbook)


class ConditionalAlertUploader(object):
    sheet_name = None

    def __init__(self, domain, langs):
        super(ConditionalAlertUploader, self).__init__()
        self.domain = domain
        self.langs = langs
        self.msgs = []

    def applies_to_rule(self, rule):
        return True

    def rule_message(self, rule):
        content = _get_rule_content(rule)
        if not isinstance(content, SMSContent):
            return {}
        return content.message

    def upload(self, workbook):
        self.msgs = []
        success_count = 0
        rows = workbook.get_worksheet(title=self.sheet_name)

        for index, row in enumerate(rows, start=2):    # one-indexed, plus header row
            rule = None
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

            if rule:
                if not isinstance(_get_rule_content(rule), SMSContent):
                    self.msgs.append((messages.error, _("Row {index} in '{sheet_name}' sheet, with rule id {id}, "
                                      "does not use SMS content.").format(index=index, id=row['id'],
                                                                          sheet_name=self.sheet_name)))
                elif self.applies_to_rule(rule):
                    with transaction.atomic():
                        dirty = self.update_rule(rule, row)
                        if dirty:
                            rule.save()
                            success_count += 1
                else:
                    self.msgs.append((messages.error, _("Rule in row {index} with id {id} does not belong in " \
                        "'{sheet_name}' sheet.".format(index=index, id=row['id'], sheet_name=self.sheet_name))))

        self.msgs.append((messages.success, _("Updated {count} rule(s) in '{sheet_name}' sheet").format(
            count=success_count, sheet_name=self.sheet_name)))

        return self.msgs

    def update_rule(self, rule, row):
        dirty = False
        if rule.name != row['name']:
            dirty = True
            rule.name = row['name']
        if rule.case_type != row['case_type']:
            dirty = True
            rule.case_type = row['case_type']
        return dirty

    def update_rule_message(self, rule, message):
        schedule = rule.get_messaging_rule_schedule()
        send_frequency = ScheduleForm.get_send_frequency_by_ui_type(schedule.ui_type)
        {
            ScheduleForm.SEND_IMMEDIATELY: lambda: None, # TODO: self.save_immediate_schedule,
            ScheduleForm.SEND_DAILY: self.save_daily_schedule,
            ScheduleForm.SEND_WEEKLY: self.save_weekly_schedule,
            ScheduleForm.SEND_MONTHLY: lambda: None, # TODO: self.save_monthly_schedule,
            ScheduleForm.SEND_CUSTOM_DAILY: lambda: None, # TODO:, self.save_custom_daily_schedule,
            ScheduleForm.SEND_CUSTOM_IMMEDIATE: lambda: None, # TODO: self.save_custom_immediate_schedule,
        }[send_frequency](schedule, message)

    def save_daily_schedule(self, schedule, message):
        TimedSchedule.assert_is(schedule)
        schedule.set_simple_daily_schedule(
            schedule.memoized_events[0],
            SMSContent(message=message),
            total_iterations=schedule.total_iterations,
            start_offset=schedule.start_offset,
            extra_options=schedule.get_extra_scheduling_options(),
            repeat_every=schedule.repeat_every,
        )

    def save_weekly_schedule(self, schedule, message):
        TimedSchedule.assert_is(schedule)
        schedule.set_simple_weekly_schedule(
            schedule.memoized_events[0],
            SMSContent(message=message),
            [e.day for e in schedule.memoized_events],
            schedule.start_day_of_week,
            total_iterations=schedule.total_iterations,
            extra_options=schedule.get_extra_scheduling_options(),
            repeat_every=schedule.repeat_every,
        )



class TranslatedConditionalAlertUploader(ConditionalAlertUploader):
    sheet_name = 'translated'

    def applies_to_rule(self, rule):
        message = self.rule_message(rule)
        return message and '*' not in message

    def update_rule(self, rule, row):
        dirty = super(TranslatedConditionalAlertUploader, self).update_rule(rule, row)
        message = self.rule_message(rule)
        message_dirty = False
        for lang in self.langs:
            if message.get(lang, '') != row['message_' + lang]:
                message.update({lang: row['message_' + lang]})
                message_dirty = True
        if message_dirty:
            self.update_rule_message(rule, message)
        return dirty or message_dirty


class UntranslatedConditionalAlertUploader(ConditionalAlertUploader):
    sheet_name = 'not translated'

    def applies_to_rule(self, rule):
        message = self.rule_message(rule)
        return not message or '*' in message

    def update_rule(self, rule, row):
        dirty = super(UntranslatedConditionalAlertUploader, self).update_rule(rule, row)
        message = self.rule_message(rule)
        if message.get('*', '') != row['message']:
            message.update({'*': row['message']})
            self.update_rule_message(rule, message)
            dirty = True
        return dirty


def _get_rule_content(rule):
    return rule.get_messaging_rule_schedule().memoized_events[0].content
