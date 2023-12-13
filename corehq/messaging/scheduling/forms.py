import json
import re
from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms.fields import (
    BooleanField,
    CharField,
    ChoiceField,
    IntegerField,
    MultipleChoiceField,
)
from django.forms.forms import Form
from django.forms.formsets import BaseFormSet, formset_factory
from django.forms.widgets import (
    CheckboxSelectMultiple,
    HiddenInput,
    Select,
    SelectMultiple,
)
from django.template.loader import render_to_string
from django.utils.functional import cached_property
from django.utils.html import escape, strip_tags
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

import bleach
from bleach.css_sanitizer import CSSSanitizer
from bs4 import BeautifulSoup
from couchdbkit import ResourceNotFound
from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from dateutil import parser
from langcodes import get_name as get_language_name
from memoized import memoized

from dimagi.utils.django.fields import TrimmedCharField

from corehq.apps.app_manager.dbaccessors import (
    get_app,
    get_latest_released_app,
)
from corehq.apps.app_manager.exceptions import FormNotFoundException
from corehq.apps.app_manager.models import AdvancedForm
from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.data_interfaces.forms import (
    CaseRuleCriteriaForm,
    validate_case_property_name,
)
from corehq.apps.data_interfaces.models import (
    CreateScheduleInstanceActionDefinition,
)
from corehq.apps.groups.models import Group
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.crispy import HQFormHelper
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.reminders.util import (
    get_combined_id,
    get_form_list,
    split_combined_id,
)
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter
from corehq.apps.sms.util import get_or_create_sms_translations
from corehq.apps.smsforms.models import SQLXFormsSession
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.models import CommCareCase
from corehq.messaging.scheduling.const import (
    ALLOWED_CSS_PROPERTIES,
    ALLOWED_HTML_ATTRIBUTES,
    ALLOWED_HTML_TAGS,
    VISIT_WINDOW_DUE_DATE,
    VISIT_WINDOW_END,
    VISIT_WINDOW_START,
)
from corehq.messaging.scheduling.exceptions import (
    ImmediateMessageEditAttempt,
    UnsupportedScheduleError,
)
from corehq.messaging.scheduling.models import (
    AlertEvent,
    AlertSchedule,
    CasePropertyTimedEvent,
    CustomContent,
    EmailContent,
    FCMNotificationContent,
    ImmediateBroadcast,
    IVRSurveyContent,
    RandomTimedEvent,
    Schedule,
    ScheduledBroadcast,
    SMSCallbackContent,
    SMSContent,
    SMSSurveyContent,
    TimedEvent,
    TimedSchedule,
)
from corehq.messaging.scheduling.scheduling_partitioned.models import (
    CaseScheduleInstanceMixin,
    ScheduleInstance,
)
from corehq.toggles import (
    EXTENSION_CASES_SYNC_ENABLED,
    FCM_NOTIFICATION,
    RICH_TEXT_EMAILS,
)


def validate_time(value):
    error = ValidationError(_("Please enter a valid 24-hour time in the format HH:MM"))

    if not isinstance(value, (str, str)) or not re.match(r'^\d?\d:\d\d$', value):
        raise error

    try:
        value = parser.parse(value)
    except ValueError:
        raise error

    return value.time()


def validate_date(value):
    error = ValidationError(_("Please enter a valid date in the format YYYY-MM-DD"))

    if not isinstance(value, (str, str)) or not re.match(r'^\d\d\d\d-\d\d-\d\d$', value):
        raise error

    try:
        value = parser.parse(value)
    except ValueError:
        raise error

    return value.date()


def validate_int(value, min_value):
    error = ValidationError(_("Please enter a whole number greater than or equal to {}").format(min_value))

    try:
        value = int(value)
    except (TypeError, ValueError):
        raise error

    if value < min_value:
        raise error

    return value


class RelaxedMultipleChoiceField(MultipleChoiceField):
    def validate(self, value):
        pass


def get_system_admin_label(data_bind=""):
    if data_bind:
        assert '"' not in data_bind, data_bind
        data_bind = ' data-bind="%s"' % data_bind
    return crispy.HTML("""
        <label class="col-xs-1 control-label"%s>
            <span class="label label-primary">%s</span>
        </label>
    """ % (data_bind, _("Requires System Admin")))


class ContentForm(Form):
    # Prefix to avoid name collisions; this means all input
    # names in the HTML are prefixed with "content-"
    prefix = 'content'

    FCM_SUBJECT_MAX_LENGTH = 255
    FCM_MESSAGE_MAX_LENGTH = 2048

    fcm_message_type = ChoiceField(
        required=False,
        choices=FCMNotificationContent.MESSAGE_TYPES,
        initial=FCMNotificationContent.MESSAGE_TYPE_NOTIFICATION,
        label=''
    )
    subject = CharField(
        required=False,
        widget=HiddenInput,
    )
    message = CharField(
        required=False,
        widget=HiddenInput,
    )
    html_message = CharField(
        required=False,
        widget=HiddenInput,
    )
    # The app id and form unique id of this form, separated by '|'
    app_and_form_unique_id = ChoiceField(
        required=False,
        label=gettext_lazy("Form"),
    )
    survey_expiration_in_hours = IntegerField(
        required=False,
        min_value=1,
        max_value=SQLXFormsSession.MAX_SESSION_LENGTH // 60,
        label='',
    )
    survey_reminder_intervals_enabled = ChoiceField(
        required=False,
        choices=(
            ('N', gettext_lazy("Disabled")),
            ('Y', gettext_lazy("Enabled")),
        ),
    )
    survey_reminder_intervals = CharField(
        required=False,
        label='',
    )
    custom_sms_content_id = ChoiceField(
        required=False,
        label=gettext_lazy("Custom SMS Content"),
        choices=[('', '')] + [(k, v[1]) for k, v in settings.AVAILABLE_CUSTOM_SCHEDULING_CONTENT.items()],
    )
    ivr_intervals = CharField(
        required=False,
        label=gettext_lazy("IVR Intervals"),
    )
    max_question_attempts = ChoiceField(
        required=False,
        label=gettext_lazy("Maximum Question Prompt Attempts"),
        choices=(
            (1, "1"),
            (2, "2"),
            (3, "3"),
            (4, "4"),
            (5, "5"),
        ),
    )
    sms_callback_intervals = CharField(
        required=False,
        label=gettext_lazy("Intervals"),
    )
    fcm_action = ChoiceField(
        required=False,
        label=gettext_lazy("Action on Notification"),
        choices=FCMNotificationContent.ACTION_CHOICES,
    )

    def __init__(self, *args, **kwargs):
        if 'schedule_form' not in kwargs:
            raise ValueError("Expected schedule_form in kwargs")

        self.schedule_form = kwargs.pop('schedule_form')
        self.domain = self.schedule_form.domain
        super(ContentForm, self).__init__(*args, **kwargs)
        self.set_app_and_form_unique_id_choices()
        self.set_message_template()

    def set_app_and_form_unique_id_choices(self):
        self.fields['app_and_form_unique_id'].choices = [('', '')] + self.schedule_form.form_choices

    def set_message_template(self):
        if RICH_TEXT_EMAILS.enabled(self.domain):
            self.fields['html_message'].initial = {
                '*': render_to_string('scheduling/partials/rich_text_email_template.html')
            }

    def clean_subject(self):
        if (self.schedule_form.cleaned_data.get('content') == ScheduleForm.CONTENT_FCM_NOTIFICATION
                and self.cleaned_data['fcm_message_type'] == FCMNotificationContent.MESSAGE_TYPE_NOTIFICATION):
            cleaned_value = self._clean_message_field('subject')
            return self._validate_fcm_message_length(cleaned_value, self.FCM_SUBJECT_MAX_LENGTH)

        if self.schedule_form.cleaned_data.get('content') != ScheduleForm.CONTENT_EMAIL:
            return None

        return self._clean_message_field('subject')

    def clean_message(self):
        if (
                RICH_TEXT_EMAILS.enabled(self.domain)
                and self.schedule_form.cleaned_data.get('content') == ScheduleForm.CONTENT_EMAIL
        ):
            return None
        if (self.schedule_form.cleaned_data.get('content') == ScheduleForm.CONTENT_FCM_NOTIFICATION
                and self.cleaned_data['fcm_message_type'] == FCMNotificationContent.MESSAGE_TYPE_NOTIFICATION):
            cleaned_value = self._clean_message_field('message')
            return self._validate_fcm_message_length(cleaned_value, self.FCM_MESSAGE_MAX_LENGTH)

        if self.schedule_form.cleaned_data.get('content') not in (ScheduleForm.CONTENT_SMS,
                                                                  ScheduleForm.CONTENT_EMAIL):
            return None

        return self._clean_message_field('message')

    def clean_html_message(self):
        if not RICH_TEXT_EMAILS.enabled(self.domain):
            return None
        return self._clean_message_field('html_message')

    def _clean_message_field(self, field_name):
        value = json.loads(self.cleaned_data[field_name])
        cleaned_value = {k: v.strip() for k, v in value.items()}

        if '*' in cleaned_value:
            if not cleaned_value['*']:
                raise ValidationError(_("This field is required"))
            return cleaned_value

        if not any(cleaned_value.values()):
            raise ValidationError(_("Please fill out at least one translation"))

        return cleaned_value

    @staticmethod
    def _validate_fcm_message_length(value, max_length):
        for data in value.values():
            if len(data) > max_length:
                raise ValidationError(_('This field must not exceed {} characters'.format(max_length)))
        return value

    def clean_fcm_message_type(self):
        if self.schedule_form.cleaned_data.get('content') != ScheduleForm.CONTENT_FCM_NOTIFICATION:
            return None

        value = self.cleaned_data.get('fcm_message_type')
        if not value:
            raise ValidationError(_("This field is required"))
        return value

    def clean_fcm_action(self):
        if self.schedule_form.cleaned_data.get('content') != ScheduleForm.CONTENT_FCM_NOTIFICATION:
            return None

        value = self.cleaned_data.get('fcm_action')
        if self.cleaned_data['fcm_message_type'] == FCMNotificationContent.MESSAGE_TYPE_DATA and not value:
            raise ValidationError(_("This field is required"))
        return value

    def clean_app_and_form_unique_id(self):
        if self.schedule_form.cleaned_data.get('content') != ScheduleForm.CONTENT_SMS_SURVEY:
            return None

        value = self.cleaned_data.get('app_and_form_unique_id')
        if not value:
            raise ValidationError(_("This field is required"))

        self.schedule_form.get_form_and_app(value)
        return value

    def clean_survey_expiration_in_hours(self):
        if self.schedule_form.cleaned_data.get('content') != ScheduleForm.CONTENT_SMS_SURVEY:
            return None

        value = self.cleaned_data.get('survey_expiration_in_hours')
        if not value:
            raise ValidationError(_("This field is required"))

        return value

    def clean_survey_reminder_intervals(self):
        if self.schedule_form.cleaned_data.get('content') != ScheduleForm.CONTENT_SMS_SURVEY:
            return None

        if self.cleaned_data.get('survey_reminder_intervals_enabled') != 'Y':
            return []

        value = self.cleaned_data.get('survey_reminder_intervals')
        if not value:
            raise ValidationError(_("Please specify the reminder intervals or disable them"))

        intervals = []
        for interval in value.split(','):
            try:
                interval = int(interval)
            except (ValueError, TypeError):
                raise ValidationError(_("Intervals must be positive numbers"))

            if interval <= 0:
                raise ValidationError(_("Intervals must be positive numbers"))

            intervals.append(interval)

        survey_expiration_in_hours = self.cleaned_data.get('survey_expiration_in_hours')
        if survey_expiration_in_hours:
            survey_expiration_in_minutes = survey_expiration_in_hours * 60
            if sum(intervals) >= survey_expiration_in_minutes:
                raise ValidationError(
                    _("Reminder intervals must add up to less than {} based "
                      "on the current survey expiration").format(survey_expiration_in_minutes)
                )

        return intervals

    def clean_custom_sms_content_id(self):
        if self.schedule_form.cleaned_data['content'] != ScheduleForm.CONTENT_CUSTOM_SMS:
            return None

        value = self.cleaned_data['custom_sms_content_id']
        if not value:
            raise ValidationError(_("This field is required"))

        return value

    def clean_ivr_intervals(self):
        if self.schedule_form.cleaned_data['content'] != ScheduleForm.CONTENT_IVR_SURVEY:
            return None

        raise NotImplementedError("IVR is no longer supported")

    def clean_max_question_attempts(self):
        if self.schedule_form.cleaned_data['content'] != ScheduleForm.CONTENT_IVR_SURVEY:
            return None

        raise NotImplementedError("IVR is no longer supported")

    def clean_sms_callback_intervals(self):
        if self.schedule_form.cleaned_data['content'] != ScheduleForm.CONTENT_SMS_CALLBACK:
            return None

        raise NotImplementedError("SMS / Callback is no longer supported")

    def distill_content(self):
        if self.schedule_form.cleaned_data['content'] == ScheduleForm.CONTENT_SMS:
            return SMSContent(
                message=self.cleaned_data['message']
            )
        elif self.schedule_form.cleaned_data['content'] == ScheduleForm.CONTENT_EMAIL:
            if RICH_TEXT_EMAILS.enabled(self.domain):
                return self._distill_rich_text_email()
            else:
                return EmailContent(
                    subject=self.cleaned_data['subject'],
                    message=self.cleaned_data['message'],
                )
        elif self.schedule_form.cleaned_data['content'] == ScheduleForm.CONTENT_SMS_SURVEY:
            combined_id = self.cleaned_data['app_and_form_unique_id']
            app_id, form_unique_id = split_combined_id(combined_id)
            return SMSSurveyContent(
                app_id=app_id,
                form_unique_id=form_unique_id,
                expire_after=self.cleaned_data['survey_expiration_in_hours'] * 60,
                reminder_intervals=self.cleaned_data['survey_reminder_intervals'],
                submit_partially_completed_forms=self.schedule_form.cleaned_data[
                    'submit_partially_completed_forms'],
                include_case_updates_in_partial_submissions=self.schedule_form.cleaned_data[
                    'include_case_updates_in_partial_submissions']
            )
        elif self.schedule_form.cleaned_data['content'] == ScheduleForm.CONTENT_CUSTOM_SMS:
            return CustomContent(
                custom_content_id=self.cleaned_data['custom_sms_content_id']
            )
        elif self.schedule_form.cleaned_data['content'] == ScheduleForm.CONTENT_FCM_NOTIFICATION:
            return FCMNotificationContent(
                subject=self.cleaned_data['subject'],
                message=self.cleaned_data['message'],
                action=self.cleaned_data['fcm_action'],
                message_type=self.cleaned_data['fcm_message_type'],
            )
        else:
            raise ValueError("Unexpected value for content: '%s'" % self.schedule_form.cleaned_data['content'])

    def _distill_rich_text_email(self):
        plaintext_message = {}
        html_message = {}
        css_sanitizer = CSSSanitizer(allowed_css_properties=ALLOWED_CSS_PROPERTIES)
        for lang, content in self.cleaned_data['html_message'].items():
            # remove everything except the body for plaintext
            soup = BeautifulSoup(content, features='lxml')
            try:
                plaintext_message[lang] = soup.find("body").get_text()
            except AttributeError:
                plaintext_message[lang] = strip_tags(content)
            html_message[lang] = bleach.clean(
                content,
                attributes=ALLOWED_HTML_ATTRIBUTES,
                tags=ALLOWED_HTML_TAGS,
                css_sanitizer=css_sanitizer,
                strip=True,
            )
        return EmailContent(
            subject=self.cleaned_data['subject'],
            message=plaintext_message,
            html_message=html_message,
        )

    def get_layout_fields(self):
        if RICH_TEXT_EMAILS.enabled(self.domain):
            message_fields = [
                hqcrispy.B3MultiField(
                    _("Rich Text Message"),
                    crispy.Field(
                        'html_message',
                        data_bind='value: html_message.htmlMessagesJSONString',
                    ),
                    crispy.Div(
                        crispy.Div(template='scheduling/partials/rich_text_message_configuration.html'),
                        data_bind='with: html_message',
                    ),
                    data_bind="visible: $root.content() === '%s' || ($root.content() === '%s' "
                    "&& fcm_message_type() === '%s')" %
                    (ScheduleForm.CONTENT_EMAIL, ScheduleForm.CONTENT_FCM_NOTIFICATION,
                     FCMNotificationContent.MESSAGE_TYPE_NOTIFICATION)
                ),
                hqcrispy.B3MultiField(
                    _("Message"),
                    crispy.Field(
                        'message',
                        data_bind='value: message.messagesJSONString',
                    ),
                    crispy.Div(
                        crispy.Div(template='scheduling/partials/message_configuration.html'),
                        data_bind='with: message',
                    ),
                    data_bind=(
                        "visible: $root.content() === '%s' || $root.content() === '%s' "
                        "|| ($root.content() === '%s' && fcm_message_type() === '%s')" %
                        (ScheduleForm.CONTENT_SMS, ScheduleForm.CONTENT_SMS_CALLBACK,
                         ScheduleForm.CONTENT_FCM_NOTIFICATION, FCMNotificationContent.MESSAGE_TYPE_NOTIFICATION)
                    ),
                )
            ]
        else:
            message_fields = [
                hqcrispy.B3MultiField(
                    _("Message"),
                    crispy.Field(
                        'message',
                        data_bind='value: message.messagesJSONString',
                    ),
                    crispy.Div(
                        crispy.Div(template='scheduling/partials/message_configuration.html'),
                        data_bind='with: message',
                    ),
                    data_bind=(
                        "visible: $root.content() === '%s' || $root.content() === '%s' "
                        "|| $root.content() === '%s' "
                        "|| ($root.content() === '%s' && fcm_message_type() === '%s')" %
                        (ScheduleForm.CONTENT_SMS, ScheduleForm.CONTENT_EMAIL, ScheduleForm.CONTENT_SMS_CALLBACK,
                         ScheduleForm.CONTENT_FCM_NOTIFICATION, FCMNotificationContent.MESSAGE_TYPE_NOTIFICATION)
                    ),
                ),
            ]

        return [
            hqcrispy.B3MultiField(
                _('Message type'),
                crispy.Field(
                    'fcm_message_type',
                    data_bind='value: fcm_message_type',
                ),
                data_bind="visible: $root.content() === '%s'" % ScheduleForm.CONTENT_FCM_NOTIFICATION,
            ),
            crispy.Div(
                crispy.Field('fcm_action'),
                data_bind="visible: $root.content() === '%s' && fcm_message_type() === '%s'"
                          % (ScheduleForm.CONTENT_FCM_NOTIFICATION, FCMNotificationContent.MESSAGE_TYPE_DATA),
            ),
            hqcrispy.B3MultiField(
                _("Subject"),
                crispy.Field(
                    'subject',
                    data_bind='value: subject.messagesJSONString',
                ),
                crispy.Div(
                    crispy.Div(template='scheduling/partials/message_configuration.html'),
                    data_bind='with: subject',
                ),
                data_bind="visible: $root.content() === '%s' || ($root.content() === '%s' "
                          "&& fcm_message_type() === '%s')" %
                          (ScheduleForm.CONTENT_EMAIL, ScheduleForm.CONTENT_FCM_NOTIFICATION,
                           FCMNotificationContent.MESSAGE_TYPE_NOTIFICATION)
            ),
            *message_fields,
            crispy.Div(
                crispy.Field(
                    'app_and_form_unique_id',
                    css_class="hqwebapp-select2",
                ),
                data_bind=(
                    "visible: $root.content() === '%s' || $root.content() === '%s'" %
                    (ScheduleForm.CONTENT_SMS_SURVEY, ScheduleForm.CONTENT_IVR_SURVEY)
                ),
            ),
            crispy.Div(
                hqcrispy.B3MultiField(
                    _("Expire After"),
                    crispy.Div(
                        twbscrispy.InlineField('survey_expiration_in_hours'),
                        css_class='col-sm-4',
                    ),
                    crispy.HTML("<span>%s</span>" % _("hour(s)")),
                ),
                hqcrispy.B3MultiField(
                    _("Reminder Intervals"),
                    crispy.Div(
                        twbscrispy.InlineField(
                            'survey_reminder_intervals_enabled',
                            data_bind='value: survey_reminder_intervals_enabled',
                        ),
                        css_class='col-sm-4',
                    ),
                    crispy.Div(
                        twbscrispy.InlineField(
                            'survey_reminder_intervals',
                            placeholder=_("e.g., 30, 60"),
                        ),
                        data_bind="visible: survey_reminder_intervals_enabled() === 'Y'",
                        css_class='col-sm-4',
                    ),
                ),
                hqcrispy.B3MultiField(
                    '',
                    crispy.HTML(
                        '<p class="help-block"><i class="fa fa-info-circle"></i> %s</p>' %
                        _("Specify a list of comma-separated intervals in minutes. At each interval, if "
                          "the survey session is still open, the system will resend the current question in the "
                          "open survey.")
                    ),
                    data_bind="visible: survey_reminder_intervals_enabled() === 'Y'",
                ),
                data_bind="visible: $root.content() === '%s'" % ScheduleForm.CONTENT_SMS_SURVEY,
            ),
            crispy.Div(
                crispy.Field('ivr_intervals'),
                crispy.Field('max_question_attempts'),
                data_bind="visible: $root.content() === '%s'" % ScheduleForm.CONTENT_IVR_SURVEY,
            ),
            crispy.Div(
                crispy.Field('sms_callback_intervals'),
                data_bind="visible: $root.content() === '%s'" % ScheduleForm.CONTENT_SMS_CALLBACK,
            ),
            hqcrispy.B3MultiField(
                _("Custom SMS Content"),
                twbscrispy.InlineField('custom_sms_content_id'),
                get_system_admin_label(),
                data_bind="visible: $root.content() === '%s'" % ScheduleForm.CONTENT_CUSTOM_SMS,
            ),
        ]

    @staticmethod
    def compute_initial(domain, content):
        """
        :param content: An instance of a subclass of corehq.messaging.scheduling.models.abstract.Content
        """
        result = {}
        if isinstance(content, SMSContent):
            result['message'] = content.message
        elif isinstance(content, EmailContent):
            result['subject'] = content.subject
            result['message'] = content.message
            result['html_message'] = content.html_message
        elif isinstance(content, SMSSurveyContent):
            result['app_and_form_unique_id'] = get_combined_id(
                content.app_id,
                content.form_unique_id
            )
            result['survey_expiration_in_hours'] = content.expire_after // 60
            if (content.expire_after % 60) != 0:
                # The old framework let you enter minutes. If it's not an even number of hours, round up.
                result['survey_expiration_in_hours'] += 1

            if content.reminder_intervals:
                result['survey_reminder_intervals_enabled'] = 'Y'
                result['survey_reminder_intervals'] = \
                    ', '.join(str(i) for i in content.reminder_intervals)
            else:
                result['survey_reminder_intervals_enabled'] = 'N'
        elif isinstance(content, CustomContent):
            result['custom_sms_content_id'] = content.custom_content_id
        elif isinstance(content, IVRSurveyContent):
            result['app_and_form_unique_id'] = get_combined_id(
                content.app_id,
                content.form_unique_id
            )
            result['ivr_intervals'] = ', '.join(str(i) for i in content.reminder_intervals)
            result['max_question_attempts'] = content.max_question_attempts
        elif isinstance(content, SMSCallbackContent):
            result['message'] = content.message
            result['sms_callback_intervals'] = ', '.join(str(i) for i in content.reminder_intervals)
        elif isinstance(content, FCMNotificationContent):
            result['subject'] = content.subject
            result['message'] = content.message
            result['fcm_action'] = content.action
            result['fcm_message_type'] = content.message_type
        else:
            raise TypeError("Unexpected content type: %s" % type(content))

        return result

    @property
    def current_values(self):
        values = {}
        for field_name in self.fields.keys():
            values[field_name] = self[field_name].value()
        return values


class CustomEventForm(ContentForm):
    # Prefix to avoid name collisions; this means all input
    # names in the HTML are prefixed with "custom-event"
    prefix = 'custom-event'

    # Corresponds to AbstractTimedEvent.day
    day = IntegerField(
        required=False,
        min_value=1,
        label='',
    )

    # Corresponds to TimedEvent.time or RandomTimedEvent.time
    time = CharField(
        required=False,
        label=gettext_lazy("HH:MM"),
    )

    # Corresponds to RandomTimedEvent.window_length
    window_length = IntegerField(
        required=False,
        min_value=1,
        max_value=1439,
        label='',
    )

    # Corresponds to CasePropertyTimedEvent.case_property_name
    case_property_name = TrimmedCharField(
        required=False,
        label='',
    )

    # Corresponds to AlertEvent.minutes_to_wait
    minutes_to_wait = IntegerField(
        required=False,
        min_value=0,
        label='',
    )

    @property
    def is_deleted(self):
        return self['DELETE'].value()

    def clean_day(self):
        if not self.schedule_form.cleaned_data_uses_timed_schedule():
            return None

        day = self.cleaned_data.get('day')
        if not isinstance(day, int):
            raise ValidationError(_("This field is required"))

        # Django handles the rest of the validation
        return day

    def clean_time(self):
        if (
            not self.schedule_form.cleaned_data_uses_timed_schedule()
            or self.schedule_form.cleaned_data.get('send_time_type') not in [
                TimedSchedule.EVENT_SPECIFIC_TIME, TimedSchedule.EVENT_RANDOM_TIME
            ]
        ):
            return None

        return validate_time(self.cleaned_data.get('time'))

    def clean_window_length(self):
        if (
            not self.schedule_form.cleaned_data_uses_timed_schedule()
            or self.schedule_form.cleaned_data.get('send_time_type') != TimedSchedule.EVENT_RANDOM_TIME
        ):
            return None

        window_length = self.cleaned_data.get('window_length')
        if not isinstance(window_length, int):
            raise ValidationError(_("This field is required"))

        # Django handles the rest of the validation
        return window_length

    def clean_case_property_name(self):
        if (
            not self.schedule_form.cleaned_data_uses_timed_schedule()
            or self.schedule_form.cleaned_data.get('send_time_type') != TimedSchedule.EVENT_CASE_PROPERTY_TIME
        ):
            return None

        return validate_case_property_name(
            self.cleaned_data.get('case_property_name'),
            allow_parent_case_references=False,
        )

    def clean_minutes_to_wait(self):
        if not self.schedule_form.cleaned_data_uses_alert_schedule():
            return None

        minutes_to_wait = self.cleaned_data.get('minutes_to_wait')
        if not isinstance(minutes_to_wait, int):
            raise ValidationError(_("This field is required"))

        # Django handles the rest of the validation
        return minutes_to_wait

    @staticmethod
    def compute_initial(domain, event):
        """
        :param event: An instance of a subclass of corehq.messaging.scheduling.models.abstract.Event
        """
        result = {}

        if isinstance(event, TimedEvent):
            result['day'] = event.day + 1
            result['time'] = event.time.strftime('%H:%M')
        elif isinstance(event, RandomTimedEvent):
            result['day'] = event.day + 1
            result['time'] = event.time.strftime('%H:%M')
            result['window_length'] = event.window_length
        elif isinstance(event, CasePropertyTimedEvent):
            result['day'] = event.day + 1
            result['case_property_name'] = event.case_property_name
        elif isinstance(event, AlertEvent):
            result['minutes_to_wait'] = event.minutes_to_wait
        else:
            raise TypeError("Unexpected event type: %s" % type(event))

        result.update(ContentForm.compute_initial(domain, event.content))

        return result

    def distill_event(self):
        if self.schedule_form.cleaned_data_uses_alert_schedule():
            return AlertEvent(
                minutes_to_wait=self.cleaned_data['minutes_to_wait'],
            )
        else:
            send_time_type = self.schedule_form.cleaned_data['send_time_type']
            day = self.cleaned_data['day'] - 1
            if send_time_type == TimedSchedule.EVENT_SPECIFIC_TIME:
                return TimedEvent(
                    day=day,
                    time=self.cleaned_data['time'],
                )
            elif send_time_type == TimedSchedule.EVENT_RANDOM_TIME:
                return RandomTimedEvent(
                    day=day,
                    time=self.cleaned_data['time'],
                    window_length=self.cleaned_data['window_length'],
                )
            elif send_time_type == TimedSchedule.EVENT_CASE_PROPERTY_TIME:
                return CasePropertyTimedEvent(
                    day=day,
                    case_property_name=self.cleaned_data['case_property_name'],
                )
            else:
                raise ValueError("Unexpected value for send_time_type: '%s'" % send_time_type)

    def get_layout_fields(self):
        return [
            crispy.Div(
                # These fields are added to the form automatically by Django when defining
                # the formset, but we still have to add them to our layout.
                crispy.Field(
                    'ORDER',
                    data_bind="value: order"
                ),
                crispy.Field(
                    'DELETE',
                    data_bind="checked: deleted"
                ),
                data_bind="visible: false"
            ),
            crispy.Div(
                hqcrispy.B3MultiField(
                    _("Event will send on day"),
                    crispy.Div(
                        twbscrispy.InlineField('day', data_bind='value: day'),
                        css_class='col-sm-4',
                    ),
                    crispy.HTML('<label class="control-label">%s</label>' % _("of the schedule")),
                ),
                hqcrispy.B3MultiField(
                    _("Time to Send"),
                    crispy.Div(
                        twbscrispy.InlineField(
                            'time',
                            data_bind='value: time, useTimePicker: true',
                        ),
                        css_class='col-sm-4',
                    ),
                    data_bind=(
                        "visible: $root.send_time_type() === '%s' || $root.send_time_type() === '%s'"
                        % (TimedSchedule.EVENT_SPECIFIC_TIME, TimedSchedule.EVENT_RANDOM_TIME)
                    )
                ),
                hqcrispy.B3MultiField(
                    _("Random Time Window Length"),
                    crispy.Div(
                        twbscrispy.InlineField('window_length'),
                        css_class='col-sm-4',
                    ),
                    data_bind="visible: $root.send_time_type() === '%s'" % TimedSchedule.EVENT_RANDOM_TIME
                ),
                hqcrispy.B3MultiField(
                    _("Send Time Case Property"),
                    crispy.Div(
                        twbscrispy.InlineField(
                            'case_property_name',
                            data_bind='value: case_property_name'
                        ),
                        css_class='col-sm-6',
                    ),
                    data_bind="visible: $root.send_time_type() === '%s'" % TimedSchedule.EVENT_CASE_PROPERTY_TIME
                ),
                data_bind="visible: $root.send_frequency() === '%s'" % ScheduleForm.SEND_CUSTOM_DAILY
            ),
            crispy.Div(
                hqcrispy.B3MultiField(
                    _("Wait"),
                    crispy.Div(
                        twbscrispy.InlineField('minutes_to_wait', data_bind='value: minutes_to_wait'),
                        css_class='col-sm-4',
                    ),
                    crispy.HTML('<label class="control-label">%s</label>' % _("minute(s) and then send")),
                ),
                data_bind="visible: $root.send_frequency() === '%s'" % ScheduleForm.SEND_CUSTOM_IMMEDIATE
            ),
        ] + super(CustomEventForm, self).get_layout_fields()

    def __init__(self, *args, **kwargs):
        super(CustomEventForm, self).__init__(*args, **kwargs)
        if self.schedule_form.editing_custom_immediate_schedule:
            self.fields['minutes_to_wait'].disabled = True

        self.helper = ScheduleForm.create_form_helper()
        self.helper.layout = crispy.Layout(
            crispy.Div(
                crispy.Fieldset(
                    '<span data-bind="template: { name: \'id_custom_event_legend\' }"></span>',
                    *self.get_layout_fields(),
                    data_bind="visible: !deleted()"
                ),
                data_bind='with: eventAndContentViewModel',
            ),
        )


class BaseCustomEventFormSet(BaseFormSet):

    def __init__(self, *args, **kwargs):
        kwargs['prefix'] = CustomEventForm.prefix
        super(BaseCustomEventFormSet, self).__init__(*args, **kwargs)

    @property
    def non_deleted_forms(self):
        return sorted(
            [form for form in self.forms if not form.is_deleted],
            key=lambda form: form.cleaned_data['ORDER']
        )

    def validate_alert_schedule_min_tick(self, custom_event_forms):
        for form in custom_event_forms[1:]:
            if form.cleaned_data['minutes_to_wait'] < 5:
                form.add_error(
                    'minutes_to_wait',
                    ValidationError(
                        _("Minutes to wait must be greater than or equal to 5 for all events after the first.")
                    )
                )

    def validate_timed_schedule_order(self, schedule_form, custom_event_forms):
        """
        We can't automatically sort the events on day and time because the
        time for some events is pulled from a case property at reminder run time.
        So we just raise an error when the events are out of order and
        let the user order them appropriately.
        """
        send_time_type = schedule_form.cleaned_data['send_time_type']
        prev_form = None
        for form in custom_event_forms:
            if prev_form:
                if send_time_type in (TimedSchedule.EVENT_SPECIFIC_TIME, TimedSchedule.EVENT_RANDOM_TIME):
                    if (
                        (form.cleaned_data['day'], form.cleaned_data['time'])
                        < (prev_form.cleaned_data['day'], prev_form.cleaned_data['time'])
                    ):
                        form.add_error(
                            'time',
                            ValidationError(
                                _("The day and time for this event are out of order. "
                                  "Please move this event into the correct order.")
                            )
                        )
                        # We have to return False and not check the rest because it will try to check
                        # the 'time' field of prev_form which has been removed from cleaned_data now
                        return False
                elif send_time_type == TimedSchedule.EVENT_CASE_PROPERTY_TIME:
                    if form.cleaned_data['day'] < prev_form.cleaned_data['day']:
                        form.add_error(
                            'day',
                            ValidationError(
                                _("The day for this event is out of order. "
                                  "Please move this event into the correct order.")
                            )
                        )
                        # We have to return False and not check the rest because it will try to check
                        # the 'day' field of prev_form which has been removed from cleaned_data now
                        return False
                else:
                    raise ValueError("Unexpected value for send_time_type: '%s'" % send_time_type)

            prev_form = form

        return True

    def validate_random_timed_events_do_not_overlap(self, schedule_form, custom_event_forms):
        if schedule_form.cleaned_data['send_time_type'] != TimedSchedule.EVENT_RANDOM_TIME:
            return True

        prev_form = None
        for form in custom_event_forms:
            if prev_form:
                prev_window_end_time = (
                    datetime(2000, 1, 1)
                    + timedelta(
                        days=prev_form.cleaned_data['day'],
                        hours=prev_form.cleaned_data['time'].hour,
                        minutes=prev_form.cleaned_data['time'].minute + prev_form.cleaned_data['window_length']
                    )
                )

                curr_window_start_time = (
                    datetime(2000, 1, 1)
                    + timedelta(
                        days=form.cleaned_data['day'],
                        hours=form.cleaned_data['time'].hour,
                        minutes=form.cleaned_data['time'].minute
                    )
                )

                if prev_window_end_time > curr_window_start_time:
                    prev_form.add_error(
                        'window_length',
                        ValidationError(
                            _("This random time window overlaps with the next event's window. "
                              "Please adjust your events accordingly to prevent overlapping windows.")
                        )
                    )
                    # We have to return False and not check the rest because it will try to check
                    # the 'window_length' field of prev_form which has been removed from cleaned_data now
                    return False

            prev_form = form

        return True

    def validate_timed_schedule_min_tick(self, schedule_form, custom_event_forms):
        if schedule_form.cleaned_data['send_time_type'] not in (
            TimedSchedule.EVENT_SPECIFIC_TIME,
            TimedSchedule.EVENT_RANDOM_TIME,
        ):
            return True

        prev_form = None
        for form in custom_event_forms:
            if prev_form:
                prev_time = (
                    datetime(2000, 1, 1)
                    + timedelta(
                        days=prev_form.cleaned_data['day'],
                        hours=prev_form.cleaned_data['time'].hour,
                        minutes=prev_form.cleaned_data['time'].minute
                    )
                )

                curr_time = (
                    datetime(2000, 1, 1)
                    + timedelta(
                        days=form.cleaned_data['day'],
                        hours=form.cleaned_data['time'].hour,
                        minutes=form.cleaned_data['time'].minute
                    )
                )

                if (curr_time - prev_time) < timedelta(minutes=5):
                    form.add_error(
                        'time',
                        ValidationError(_("Events must occur at least 5 minutes apart."))
                    )
                    # We have to return False and not check the rest because it will try to check
                    # the 'time' field of prev_form which has been removed from cleaned_data now
                    return False

            prev_form = form

        return True

    def validate_repeat_every_on_schedule_form(self, schedule_form, custom_event_forms):
        if schedule_form.cleaned_data_uses_alert_schedule():
            return True

        # Don't bother validating this unless the schedule_form is valid
        if not super(ScheduleForm, schedule_form).is_valid():
            return False

        if schedule_form.distill_total_iterations() == 1:
            return True

        last_day = custom_event_forms[-1].cleaned_data['day']
        if last_day > schedule_form.distill_repeat_every():
            raise ValidationError(
                _("There is a mismatch between the last event's day and how often you have "
                  "chosen to repeat the schedule above. Based on the day of the last event, "
                  "you must repeat every {} days at a minimum.").format(last_day)
            )

        return True

    def clean(self):
        non_deleted_forms = self.non_deleted_forms

        if any(form.errors for form in non_deleted_forms):
            return

        if len(non_deleted_forms) == 0:
            raise ValidationError(_("Please add at least one event"))

        schedule_form = non_deleted_forms[0].schedule_form
        if schedule_form.cleaned_data_uses_alert_schedule():
            self.validate_alert_schedule_min_tick(non_deleted_forms)
        elif schedule_form.cleaned_data_uses_timed_schedule():
            # Use short-circuiting to only continue validating if the previous
            # validation passes
            (self.validate_timed_schedule_order(schedule_form, non_deleted_forms)
             and self.validate_random_timed_events_do_not_overlap(schedule_form, non_deleted_forms)
             and self.validate_timed_schedule_min_tick(schedule_form, non_deleted_forms)
             and self.validate_repeat_every_on_schedule_form(schedule_form, non_deleted_forms))
        else:
            raise ValueError("Unexpected schedule type")


class ScheduleForm(Form):
    # Prefix to avoid name collisions; this means all input
    # names in the HTML are prefixed with "schedule-"
    prefix = "schedule"

    SEND_DAILY = 'daily'
    SEND_WEEKLY = 'weekly'
    SEND_MONTHLY = 'monthly'
    SEND_IMMEDIATELY = 'immediately'
    SEND_CUSTOM_DAILY = 'custom_daily'
    SEND_CUSTOM_IMMEDIATE = 'custom_immediate'

    STOP_AFTER_OCCURRENCES = 'after_occurrences'
    STOP_NEVER = 'never'

    CONTENT_SMS = 'sms'
    CONTENT_EMAIL = 'email'
    CONTENT_SMS_SURVEY = 'sms_survey'
    CONTENT_IVR_SURVEY = 'ivr_survey'
    CONTENT_SMS_CALLBACK = 'sms_callback'
    CONTENT_CUSTOM_SMS = 'custom_sms'
    CONTENT_FCM_NOTIFICATION = 'fcm_notification'

    YES = 'Y'
    NO = 'N'
    JSON = 'J'

    REPEAT_NO = 'no'
    REPEAT_EVERY_1 = 'repeat_every_1'
    REPEAT_EVERY_N = 'repeat_every_n'

    LANGUAGE_PROJECT_DEFAULT = 'PROJECT_DEFAULT'

    send_frequency = ChoiceField(
        required=True,
        label=gettext_lazy('Send'),
        choices=(
            (SEND_IMMEDIATELY, gettext_lazy('Immediately')),
            (SEND_DAILY, gettext_lazy('Daily')),
            (SEND_WEEKLY, gettext_lazy('Weekly')),
            (SEND_MONTHLY, gettext_lazy('Monthly')),
            (SEND_CUSTOM_DAILY, gettext_lazy('Custom Daily Schedule')),
            (SEND_CUSTOM_IMMEDIATE, gettext_lazy('Custom Immediate Schedule')),
        )
    )
    active = ChoiceField(
        required=True,
        label=gettext_lazy('Status'),
        choices=(
            ('Y', gettext_lazy("Active")),
            ('N', gettext_lazy("Inactive")),
        ),
    )
    weekdays = MultipleChoiceField(
        required=False,
        label=gettext_lazy('On'),
        choices=(
            ('6', gettext_lazy('Sunday')),
            ('0', gettext_lazy('Monday')),
            ('1', gettext_lazy('Tuesday')),
            ('2', gettext_lazy('Wednesday')),
            ('3', gettext_lazy('Thursday')),
            ('4', gettext_lazy('Friday')),
            ('5', gettext_lazy('Saturday')),
        ),
        widget=CheckboxSelectMultiple()
    )
    days_of_month = MultipleChoiceField(
        required=False,
        label=gettext_lazy('On Days'),
        choices=(
            # The actual choices are rendered by a template
            tuple((str(x), '') for x in range(-3, 29) if x)
        )
    )
    send_time_type = ChoiceField(
        required=True,
        choices=(
            (TimedSchedule.EVENT_SPECIFIC_TIME, gettext_lazy("A specific time")),
            (TimedSchedule.EVENT_RANDOM_TIME, gettext_lazy("A random time")),
        )
    )
    send_time = CharField(required=False, label=gettext_lazy("HH:MM"))
    window_length = IntegerField(
        required=False,
        min_value=1,
        max_value=1439,
        label='',
    )
    start_date = CharField(
        label='',
        required=False
    )
    repeat = ChoiceField(
        required=False,
        # The text for REPEAT_EVERY_1 gets set dynamically
        choices=(
            (REPEAT_NO, gettext_lazy('no')),
            (REPEAT_EVERY_1, ''),
            (REPEAT_EVERY_N, gettext_lazy('every')),
        ),
    )
    repeat_every = IntegerField(
        required=False,
        min_value=2,
        label='',
    )
    stop_type = ChoiceField(
        required=False,
        choices=(
            (STOP_AFTER_OCCURRENCES, gettext_lazy('after')),
            (STOP_NEVER, gettext_lazy('never')),
        )
    )
    occurrences = IntegerField(
        required=False,
        min_value=2,
        label='',
    )
    recipient_types = MultipleChoiceField(
        required=True,
        label=gettext_lazy('Recipient(s)'),
        choices=(
            (ScheduleInstance.RECIPIENT_TYPE_MOBILE_WORKER, gettext_lazy("Users")),
            (ScheduleInstance.RECIPIENT_TYPE_USER_GROUP, gettext_lazy("User Groups")),
            (ScheduleInstance.RECIPIENT_TYPE_LOCATION, gettext_lazy("User Organizations")),
            (ScheduleInstance.RECIPIENT_TYPE_CASE_GROUP, gettext_lazy("Case Groups")),
        )
    )
    user_recipients = RelaxedMultipleChoiceField(
        required=False,
        label=gettext_lazy("User Recipient(s)"),
        widget=SelectMultiple(choices=[]),
    )
    user_group_recipients = RelaxedMultipleChoiceField(
        required=False,
        label=gettext_lazy("User Group Recipient(s)"),
        widget=SelectMultiple(choices=[]),
    )
    user_organization_recipients = RelaxedMultipleChoiceField(
        required=False,
        label=gettext_lazy("User Organization Recipient(s)"),
        widget=SelectMultiple(choices=[]),
        help_text=ExpandedMobileWorkerFilter.location_search_help,
    )
    include_descendant_locations = BooleanField(
        required=False,
        label=gettext_lazy("Also send to users at organizations below the selected ones"),
    )
    restrict_location_types = ChoiceField(
        required=False,
        choices=(
            ('N', gettext_lazy("Users at all organization levels")),
            ('Y', gettext_lazy("Only users at the following organization levels")),
        ),
    )
    location_types = RelaxedMultipleChoiceField(
        required=False,
        label='',
        widget=SelectMultiple(choices=[]),
    )
    case_group_recipients = RelaxedMultipleChoiceField(
        required=False,
        label=gettext_lazy("Case Group Recipient(s)"),
        widget=SelectMultiple(choices=[]),
    )
    content = ChoiceField(
        required=True,
        label=gettext_lazy("What to send"),
        choices=(
            (CONTENT_SMS, gettext_lazy('SMS')),
            (CONTENT_EMAIL, gettext_lazy('Email')),
        )
    )
    default_language_code = ChoiceField(
        required=True,
        label=gettext_lazy("Default Language"),
    )
    submit_partially_completed_forms = BooleanField(
        required=False,
        label=gettext_lazy("When the survey session expires, submit a partially "
                           "completed form if the survey is not completed"),
    )
    include_case_updates_in_partial_submissions = BooleanField(
        required=False,
        label=gettext_lazy("Include case updates in partially completed submissions"),
    )

    use_utc_as_default_timezone = BooleanField(
        required=False,
        label=gettext_lazy("Interpret send times using GMT when recipient has no preferred time zone"),
    )

    # The standalone_content_form should be an instance of ContentForm and is used
    # for defining the content used with any of the predefined schedule types (Immediate,
    # Daily, Weekly, or Monthly).
    standalone_content_form = None

    custom_event_formset = None

    # The custom immediate schedule use case doesn't make sense for broadcasts
    allow_custom_immediate_schedule = False

    use_user_data_filter = ChoiceField(
        label='',
        choices=(
            (NO, gettext_lazy("No")),
            (YES, gettext_lazy("Yes")),
        ),
        required=False,
    )

    user_data_property_name = TrimmedCharField(
        label=gettext_lazy("User data filter: property name"),
        required=False,
    )

    user_data_property_value = TrimmedCharField(
        label=gettext_lazy("User data filter: property value"),
        required=False,
    )

    use_advanced_user_data_filter = True

    @classmethod
    def get_send_frequency_by_ui_type(cls, ui_type):
        return {
            Schedule.UI_TYPE_IMMEDIATE: cls.SEND_IMMEDIATELY,
            Schedule.UI_TYPE_DAILY: cls.SEND_DAILY,
            Schedule.UI_TYPE_WEEKLY: cls.SEND_WEEKLY,
            Schedule.UI_TYPE_MONTHLY: cls.SEND_MONTHLY,
            Schedule.UI_TYPE_CUSTOM_DAILY: cls.SEND_CUSTOM_DAILY,
            Schedule.UI_TYPE_CUSTOM_IMMEDIATE: cls.SEND_CUSTOM_IMMEDIATE,
            Schedule.UI_TYPE_UNKNOWN: None,
        }[ui_type]

    def is_valid(self):
        # Make sure .is_valid() is called on all appropriate forms before returning.
        # Don't let the result of one short-circuit the expression and prevent calling the others.

        schedule_form_is_valid = super(ScheduleForm, self).is_valid()
        custom_event_formset_is_valid = self.custom_event_formset.is_valid()
        standalone_content_form_is_valid = self.standalone_content_form.is_valid()

        if self.cleaned_data_uses_custom_event_definitions():
            return schedule_form_is_valid and custom_event_formset_is_valid
        else:
            return schedule_form_is_valid and standalone_content_form_is_valid

    def update_send_frequency_choices(self, initial_value):
        def filter_function(two_tuple):
            if (
                not self.allow_custom_immediate_schedule
                and two_tuple[0] == self.SEND_CUSTOM_IMMEDIATE
            ):
                return False

            if initial_value:
                if initial_value == self.SEND_IMMEDIATELY:
                    return two_tuple[0] == self.SEND_IMMEDIATELY
                elif initial_value == self.SEND_CUSTOM_IMMEDIATE:
                    return two_tuple[0] == self.SEND_CUSTOM_IMMEDIATE
                else:
                    return two_tuple[0] not in (self.SEND_IMMEDIATELY, self.SEND_CUSTOM_IMMEDIATE)

            return True

        self.fields['send_frequency'].choices = list(filter(filter_function,
                                                            self.fields['send_frequency'].choices))

    def set_default_language_code_choices(self):
        choices = [
            (self.LANGUAGE_PROJECT_DEFAULT, _("Project Default")),
        ]

        for language_code in self.language_list:
            language_name = get_language_name(language_code)
            if language_name:
                language_name = _(language_name)
            else:
                language_name = language_code

            choices.append((language_code, language_name))

        self.fields['default_language_code'].choices = choices

    def add_initial_for_immediate_schedule(self, initial):
        initial['send_frequency'] = self.SEND_IMMEDIATELY

    def add_initial_for_daily_schedule(self, initial):
        initial['send_frequency'] = self.SEND_DAILY

    def add_initial_for_weekly_schedule(self, initial):
        weekdays = self.initial_schedule.get_weekdays()
        initial['send_frequency'] = self.SEND_WEEKLY
        initial['weekdays'] = [str(day) for day in weekdays]

    def add_initial_for_monthly_schedule(self, initial):
        initial['send_frequency'] = self.SEND_MONTHLY
        initial['days_of_month'] = [str(e.day) for e in self.initial_schedule.memoized_events]

    def add_initial_for_custom_daily_schedule(self, initial):
        initial['send_frequency'] = self.SEND_CUSTOM_DAILY
        initial['custom_event_formset'] = [
            CustomEventForm.compute_initial(self.domain, event)
            for event in self.initial_schedule.memoized_events
        ]

    def add_initial_for_custom_immediate_schedule(self, initial):
        initial['send_frequency'] = self.SEND_CUSTOM_IMMEDIATE
        initial['custom_event_formset'] = [
            CustomEventForm.compute_initial(self.domain, event)
            for event in self.initial_schedule.memoized_events
        ]

    def add_initial_for_send_time(self, initial):
        if initial['send_frequency'] not in (self.SEND_DAILY, self.SEND_WEEKLY, self.SEND_MONTHLY):
            return

        if self.initial_schedule.event_type == TimedSchedule.EVENT_SPECIFIC_TIME:
            initial['send_time'] = self.initial_schedule.memoized_events[0].time.strftime('%H:%M')
        elif self.initial_schedule.event_type == TimedSchedule.EVENT_RANDOM_TIME:
            initial['send_time'] = self.initial_schedule.memoized_events[0].time.strftime('%H:%M')
            initial['window_length'] = self.initial_schedule.memoized_events[0].window_length
        else:
            raise ValueError("Unexpected event_type: %s" % self.initial_schedule.event_type)

    def add_initial_for_timed_schedule(self, initial):
        initial['send_time_type'] = self.initial_schedule.event_type

        self.add_initial_for_send_time(initial)

        if self.initial_schedule.total_iterations == 1:
            initial['repeat'] = self.REPEAT_NO
        else:
            if initial['send_frequency'] in (self.SEND_DAILY, self.SEND_CUSTOM_DAILY):
                repeat_every = self.initial_schedule.repeat_every
            elif initial['send_frequency'] == self.SEND_WEEKLY:
                repeat_every = self.initial_schedule.repeat_every // 7
            elif initial['send_frequency'] == self.SEND_MONTHLY:
                repeat_every = self.initial_schedule.repeat_every * -1
            else:
                raise ValueError("Unexpected value for send_frequency: %s" % initial['send_frequency'])

            if repeat_every == 1:
                initial['repeat'] = self.REPEAT_EVERY_1
            else:
                initial['repeat'] = self.REPEAT_EVERY_N
                initial['repeat_every'] = repeat_every

            if self.initial_schedule.total_iterations == TimedSchedule.REPEAT_INDEFINITELY:
                initial['stop_type'] = self.STOP_NEVER
            elif self.initial_schedule.total_iterations > 1:
                initial['stop_type'] = self.STOP_AFTER_OCCURRENCES
                initial['occurrences'] = self.initial_schedule.total_iterations

    def add_initial_recipients(self, recipients, initial):
        recipient_types = set()
        user_recipients = []
        user_group_recipients = []
        user_organization_recipients = []
        case_group_recipients = []

        for recipient_type, recipient_id in recipients:
            recipient_types.add(recipient_type)
            if recipient_type == ScheduleInstance.RECIPIENT_TYPE_MOBILE_WORKER:
                user_recipients.append(recipient_id)
            elif recipient_type == ScheduleInstance.RECIPIENT_TYPE_USER_GROUP:
                user_group_recipients.append(recipient_id)
            elif recipient_type == ScheduleInstance.RECIPIENT_TYPE_LOCATION:
                user_organization_recipients.append(recipient_id)
            elif recipient_type == ScheduleInstance.RECIPIENT_TYPE_CASE_GROUP:
                case_group_recipients.append(recipient_id)

        initial.update({
            'recipient_types': list(recipient_types),
            'user_recipients': user_recipients,
            'user_group_recipients': user_group_recipients,
            'user_organization_recipients': user_organization_recipients,
            'case_group_recipients': case_group_recipients,
            'include_descendant_locations': self.initial_schedule.include_descendant_locations,
            'restrict_location_types': 'Y' if len(self.initial_schedule.location_type_filter) > 0 else 'N',
            'location_types': [str(i) for i in self.initial_schedule.location_type_filter],
        })

    def add_initial_for_content(self, initial):
        """
        Add initial values for content-related fields that are shared across
        all events in the schedule, whether it's a custom schedule or not.
        """
        content = self.initial_schedule.memoized_events[0].content

        if isinstance(content, SMSContent):
            initial['content'] = self.CONTENT_SMS
        elif isinstance(content, EmailContent):
            initial['content'] = self.CONTENT_EMAIL
        elif isinstance(content, SMSSurveyContent):
            initial['content'] = self.CONTENT_SMS_SURVEY
            initial['submit_partially_completed_forms'] = content.submit_partially_completed_forms
            initial['include_case_updates_in_partial_submissions'] = \
                content.include_case_updates_in_partial_submissions
        elif isinstance(content, CustomContent):
            initial['content'] = self.CONTENT_CUSTOM_SMS
        elif isinstance(content, IVRSurveyContent):
            initial['content'] = self.CONTENT_IVR_SURVEY
            initial['submit_partially_completed_forms'] = content.submit_partially_completed_forms
            initial['include_case_updates_in_partial_submissions'] = \
                content.include_case_updates_in_partial_submissions
        elif isinstance(content, SMSCallbackContent):
            initial['content'] = self.CONTENT_SMS_CALLBACK
        elif isinstance(content, FCMNotificationContent):
            initial['content'] = self.CONTENT_FCM_NOTIFICATION
        else:
            raise TypeError("Unexpected content type: %s" % type(content))

    def compute_initial(self, domain):
        result = {}
        schedule = self.initial_schedule
        if schedule:
            result['active'] = 'Y' if schedule.active else 'N'
            result['default_language_code'] = (
                schedule.default_language_code
                if schedule.default_language_code
                else self.LANGUAGE_PROJECT_DEFAULT
            )
            if schedule.user_data_filter:
                # The only structure created with these UIs is of the form
                # {name: [value]} or {name: [value1, value2, ...]}
                # See Schedule.user_data_filter for an explanation of the full possible
                # structure.
                name = list(schedule.user_data_filter)[0]
                values = schedule.user_data_filter[name]
                choice = self.YES if len(values) == 1 else self.JSON
                value = values[0] if len(values) == 1 else json.dumps(values)
                result['use_user_data_filter'] = choice
                result['user_data_property_name'] = name
                result['user_data_property_value'] = value

            result['use_utc_as_default_timezone'] = schedule.use_utc_as_default_timezone
            if isinstance(schedule, AlertSchedule):
                if schedule.ui_type == Schedule.UI_TYPE_IMMEDIATE:
                    self.add_initial_for_immediate_schedule(result)
                elif schedule.ui_type == Schedule.UI_TYPE_CUSTOM_IMMEDIATE:
                    self.add_initial_for_custom_immediate_schedule(result)
                else:
                    raise UnsupportedScheduleError(
                        "Unexpected Schedule ui_type '%s' for AlertSchedule '%s'" %
                        (schedule.ui_type, schedule.schedule_id)
                    )
            elif isinstance(schedule, TimedSchedule):
                if schedule.ui_type == Schedule.UI_TYPE_DAILY:
                    self.add_initial_for_daily_schedule(result)
                elif schedule.ui_type == Schedule.UI_TYPE_WEEKLY:
                    self.add_initial_for_weekly_schedule(result)
                elif schedule.ui_type == Schedule.UI_TYPE_MONTHLY:
                    self.add_initial_for_monthly_schedule(result)
                elif schedule.ui_type == Schedule.UI_TYPE_CUSTOM_DAILY:
                    self.add_initial_for_custom_daily_schedule(result)
                else:
                    raise UnsupportedScheduleError(
                        "Unexpected Schedule ui_type '%s' for TimedSchedule '%s'" %
                        (schedule.ui_type, schedule.schedule_id)
                    )

                self.add_initial_for_timed_schedule(result)

            self.add_initial_for_content(result)

        return result

    @property
    def editing_custom_immediate_schedule(self):
        """
        The custom immediate schedule is provided for backwards-compatibility with
        the old framework which allowed that use case. It's not as useful of a
        feature as the custom daily schedule, and the framework isn't currently
        responsive to changes in the custom immediate schedule's events (and neither
        was the old framework), so we restrict certain parts of the UI when editing
        a custom immediate schedule.

        If these edit options are deemed to be useful, then the framework should
        be updated to be responsive to changes in an AlertSchedule's AlertEvents.
        This would include capturing a start_timestamp and schedule_revision on
        the AbstractAlertScheduleInstance, similar to what is done for the
        AbstractTimedScheduleInstance.
        """
        return self.initial_schedule and self.initial_schedule.ui_type == Schedule.UI_TYPE_CUSTOM_IMMEDIATE

    @memoized
    def get_form_and_app(self, app_and_form_unique_id):
        """
        Returns the form and app associated with the primary application
        document (i.e., not a build).
        """
        error_msg = _("Please choose a form")
        try:
            app_id, form_unique_id = split_combined_id(app_and_form_unique_id)
            app = get_app(self.domain, app_id)
            form = app.get_form(form_unique_id)
        except Exception:
            raise ValidationError(error_msg)

        return form, app

    @memoized
    def get_latest_released_form_and_app(self, app_id, form_unique_id):
        """
        Returns the form and app associated with the latest released
        build of an app.
        """
        latest_released_app = get_latest_released_app(self.domain, app_id)
        if latest_released_app is None:
            raise ValidationError(_("Please make a released build of the application"))

        try:
            latest_released_form = latest_released_app.get_form(form_unique_id)
        except FormNotFoundException:
            raise ValidationError(_("Form not found in latest released app build"))

        return latest_released_form, latest_released_app

    def __init__(self, domain, schedule, can_use_sms_surveys, *args, **kwargs):
        self.domain = domain
        self.initial_schedule = schedule
        self.can_use_sms_surveys = can_use_sms_surveys
        self.is_system_admin = kwargs.pop("is_system_admin")

        if kwargs.get('initial'):
            raise ValueError("Initial values are set by the form")

        schedule_form_initial = {}
        standalone_content_form_initial = {}
        if schedule:
            schedule_form_initial = self.compute_initial(domain)
            if schedule.ui_type in (
                Schedule.UI_TYPE_IMMEDIATE,
                Schedule.UI_TYPE_DAILY,
                Schedule.UI_TYPE_WEEKLY,
                Schedule.UI_TYPE_MONTHLY,
            ):
                standalone_content_form_initial = ContentForm.compute_initial(domain,
                                                                              schedule.memoized_events[0].content)

        super(ScheduleForm, self).__init__(*args, initial=schedule_form_initial, **kwargs)
        self.standalone_content_form = ContentForm(
            *args,
            schedule_form=self,
            initial=standalone_content_form_initial,
            **kwargs
        )

        CustomEventFormSet = formset_factory(
            CustomEventForm,
            formset=BaseCustomEventFormSet,
            extra=0,
            can_order=True,
            can_delete=True,
        )
        self.custom_event_formset = CustomEventFormSet(
            *args,
            form_kwargs={'schedule_form': self},
            initial=schedule_form_initial.get('custom_event_formset', []),
            **kwargs
        )

        self.add_additional_content_types()
        self.set_default_language_code_choices()
        self.update_send_frequency_choices(schedule_form_initial.get('send_frequency'))
        self.enable_json_user_data_filter(schedule_form_initial)

        self.before_content = self.create_form_helper()
        self.before_content.layout = crispy.Layout(*self.get_before_content_layout_fields())

        self.standalone_content_form.helper = self.create_form_helper()
        self.standalone_content_form.helper.layout = crispy.Layout(
            crispy.Fieldset(
                '',
                crispy.Div(
                    *self.standalone_content_form.get_layout_fields(),
                    data_bind=(
                        "with: standalone_content_form, visible: !$root.usesCustomEventDefinitions()"
                    )
                ),
            ),
        )

        self.after_content = self.create_form_helper()
        self.after_content.layout = crispy.Layout(*self.get_after_content_layout_fields())

    @staticmethod
    def create_form_helper():
        helper = HQFormHelper()
        helper.form_tag = False
        return helper

    @cached_property
    def form_choices(self):
        return [(form['code'], form['name']) for form in get_form_list(self.domain)]

    def add_additional_content_types(self):
        if (
            self.can_use_sms_surveys
            or (self.initial_schedule and self.initial_schedule.memoized_uses_sms_survey)
        ):
            self.fields['content'].choices += [
                (self.CONTENT_SMS_SURVEY, _("SMS Survey")),
            ]

        if self.initial_schedule:
            if self.initial_schedule.memoized_uses_ivr_survey:
                self.fields['content'].choices += [
                    (self.CONTENT_IVR_SURVEY, _("IVR Survey")),
                ]

            if self.initial_schedule.memoized_uses_sms_callback:
                self.fields['content'].choices += [
                    (self.CONTENT_SMS_CALLBACK, _("SMS Expecting Callback")),
                ]

    def enable_json_user_data_filter(self, initial):
        if self.is_system_admin or initial.get('use_user_data_filter') == self.JSON:
            self.fields['use_user_data_filter'].choices += [
                (self.JSON, _("JSON: list of strings")),
            ]

    @property
    def scheduling_fieldset_legend(self):
        return _("Scheduling")

    def get_before_content_layout_fields(self):
        return [
            crispy.Fieldset(
                _("Scheduling"),
                crispy.Field('active'),
            ),
            crispy.Fieldset(
                self.scheduling_fieldset_legend,
                *self.get_scheduling_layout_fields()
            ),
            crispy.Fieldset(
                _("Recipients"),
                *self.get_recipients_layout_fields()
            ),
            crispy.Fieldset(
                _("Content"),
                crispy.Field('content', data_bind='value: content'),
                hqcrispy.B3MultiField(
                    '',
                    crispy.HTML(
                        '<span data-bind="click: addCustomEvent" class="btn btn-primary">'
                        '<i class="fa fa-plus"></i> %s</span>'
                        % _("Add Event")
                    ),
                    data_bind="visible: usesCustomEventDefinitions() && !editing_custom_immediate_schedule()"
                ),
            ),
        ]

    def get_after_content_layout_fields(self):
        return [
            crispy.Fieldset(
                _("Advanced Survey Options"),
                *self.get_advanced_survey_layout_fields(),
                data_bind=(
                    "visible: content() === '%s' || content() === '%s'" %
                    (self.CONTENT_SMS_SURVEY, self.CONTENT_IVR_SURVEY)
                )
            ),
            crispy.Fieldset(
                _("Advanced"),
                *self.get_advanced_layout_fields()
            ),
        ]

    def get_start_date_layout_fields(self):
        raise NotImplementedError()

    def get_extra_timing_fields(self):
        return []

    def get_scheduling_layout_fields(self):
        result = [
            crispy.Field(
                'send_frequency',
                data_bind='value: send_frequency',
            ),
            crispy.Div(
                crispy.Field(
                    'weekdays',
                    data_bind='checked: weekdays',
                ),
                data_bind='visible: showWeekdaysInput',
            ),
            hqcrispy.B3MultiField(
                _("On Days"),
                crispy.Field(
                    'days_of_month',
                    template='scheduling/partials/days_of_month_picker.html',
                ),
                data_bind='visible: showDaysOfMonthInput',
            ),
            hqcrispy.B3MultiField(
                _("At"),
                crispy.Div(
                    twbscrispy.InlineField(
                        'send_time_type',
                        data_bind='value: send_time_type',
                    ),
                    css_class='col-sm-4',
                ),
                crispy.Div(
                    crispy.Div(
                        twbscrispy.InlineField(
                            'send_time',
                            data_bind="value: send_time, useTimePicker: true"
                        ),
                        css_class='col-sm-4',
                        data_bind=("visible: send_time_type() === '%s' || send_time_type() === '%s'"
                                   % (TimedSchedule.EVENT_SPECIFIC_TIME, TimedSchedule.EVENT_RANDOM_TIME)),
                    ),
                    *self.get_extra_timing_fields(),
                    data_bind="visible: showSharedTimeInput"
                ),
                crispy.Div(
                    crispy.HTML(
                        '<p class="help-block"><i class="fa fa-info-circle"></i> %s</p>' %
                        _("Define the send times in the events below.")
                    ),
                    data_bind="visible: send_frequency() === '%s'" % self.SEND_CUSTOM_DAILY,
                ),
                data_bind="visible: usesTimedSchedule()"
            ),
            hqcrispy.B3MultiField(
                _("Random Window Length (minutes)"),
                crispy.Div(
                    crispy.Field('window_length'),
                ),
                data_bind=("visible: showSharedTimeInput() && send_time_type() === '%s'"
                           % TimedSchedule.EVENT_RANDOM_TIME),
            ),
        ]

        result.extend(self.get_start_date_layout_fields())

        result.extend([
            hqcrispy.B3MultiField(
                _("Repeat"),
                crispy.Div(
                    twbscrispy.InlineField(
                        'repeat',
                        data_bind='value: repeat',
                    ),
                    css_class='col-sm-4',
                ),
                crispy.Div(
                    twbscrispy.InlineField(
                        'repeat_every',
                        data_bind='value: repeat_every',
                    ),
                    css_class='col-sm-2',
                    data_bind="visible: repeat() === '%s'" % self.REPEAT_EVERY_N,
                ),
                crispy.Div(
                    crispy.Div(
                        crispy.HTML('<label class="control-label">%s</label>' % _("days")),
                        css_class='col-sm-4',
                        data_bind="visible: send_frequency() === '%s' || send_frequency() === '%s'" % (
                            self.SEND_DAILY, self.SEND_CUSTOM_DAILY,
                        )
                    ),
                    crispy.Div(
                        crispy.HTML('<label class="control-label">%s</label>' % _("weeks")),
                        css_class='col-sm-4',
                        data_bind="visible: send_frequency() === '%s'" % self.SEND_WEEKLY,
                    ),
                    crispy.Div(
                        crispy.HTML('<label class="control-label">%s</label>' % _("months")),
                        css_class='col-sm-4',
                        data_bind="visible: send_frequency() === '%s'" % self.SEND_MONTHLY,
                    ),
                    data_bind="visible: repeat() === '%s'" % self.REPEAT_EVERY_N,
                ),
                data_bind='visible: usesTimedSchedule()',
            ),
            hqcrispy.B3MultiField(
                _("Stop"),
                crispy.Div(
                    twbscrispy.InlineField(
                        'stop_type',
                        data_bind='value: stop_type',
                    ),
                    css_class='col-sm-4',
                ),
                crispy.Div(
                    twbscrispy.InlineField(
                        'occurrences',
                        data_bind='value: occurrences',
                    ),
                    css_class='col-sm-2',
                    data_bind="visible: stop_type() === '%s'" % self.STOP_AFTER_OCCURRENCES,
                ),
                crispy.Div(
                    crispy.Div(
                        crispy.HTML('<label class="control-label">%s</label>' % _("occurrences")),
                        css_class='col-sm-4',
                        data_bind="visible: send_frequency() === '%s' || send_frequency() === '%s'" % (
                            self.SEND_DAILY, self.SEND_CUSTOM_DAILY
                        )
                    ),
                    crispy.Div(
                        crispy.HTML('<label class="control-label">%s</label>' % _("weekly occurrences")),
                        css_class='col-sm-4',
                        data_bind="visible: send_frequency() === '%s'" % self.SEND_WEEKLY,
                    ),
                    crispy.Div(
                        crispy.HTML('<label class="control-label">%s</label>' % _("monthly occurrences")),
                        css_class='col-sm-4',
                        data_bind="visible: send_frequency() === '%s'" % self.SEND_MONTHLY,
                    ),
                    data_bind="visible: stop_type() === '%s'" % self.STOP_AFTER_OCCURRENCES,
                ),
                data_bind="visible: usesTimedSchedule() && repeat() !== '%s'" % self.REPEAT_NO,
            ),
            hqcrispy.B3MultiField(
                "",
                crispy.HTML(
                    '<span>%s</span> <span data-bind="text: computedEndDate"></span>'
                    % _("Date of final occurrence:"),
                ),
                data_bind="visible: computedEndDate() !== ''",
            ),
        ])

        return result

    def get_recipients_layout_fields(self):
        return [
            crispy.Field(
                'recipient_types',
                data_bind="selectedOptions: recipient_types",
                style="width: 100%;"
            ),
            crispy.Div(
                crispy.HTML(
                    """
                        <p id="parent-case-type-warning" class="help-block alert alert-info">
                        <i class="fa fa-info-circle"></i>
                            %s
                        </p>
                    """
                    % _(
                        """
                            The "Case's Parent Case" Recipient setting only works for Parent / Child relationships,
                            not Parent / Extension or Host / Extension relationships.
                        """
                    )),
                data_bind="visible: (recipientTypeSelected('{parentCase}') && {extensionFlagEnabled})".format(
                    parentCase=CaseScheduleInstanceMixin.RECIPIENT_TYPE_PARENT_CASE,
                    extensionFlagEnabled="true" if EXTENSION_CASES_SYNC_ENABLED.enabled(self.domain) else "false")
            ),
            crispy.Div(
                crispy.Field(
                    'user_recipients',
                    data_bind='value: user_recipients.value',
                    placeholder=_("Select mobile worker(s)")
                ),
                data_bind="visible: recipientTypeSelected('%s')" % ScheduleInstance.RECIPIENT_TYPE_MOBILE_WORKER,
            ),
            crispy.Div(
                crispy.Field(
                    'user_group_recipients',
                    data_bind='value: user_group_recipients.value',
                    placeholder=_("Select user group(s)")
                ),
                data_bind="visible: recipientTypeSelected('%s')" % ScheduleInstance.RECIPIENT_TYPE_USER_GROUP,
            ),
            crispy.Div(
                crispy.Field(
                    'user_organization_recipients',
                    data_bind='value: user_organization_recipients.value',
                    placeholder=_("Select user organization(s)")
                ),
                crispy.Field(
                    'include_descendant_locations',
                    data_bind='checked: include_descendant_locations',
                ),
                hqcrispy.B3MultiField(
                    _("For the selected organizations, include"),
                    crispy.Div(
                        twbscrispy.InlineField(
                            'restrict_location_types',
                            data_bind='value: restrict_location_types',
                        ),
                        css_class='col-sm-6',
                    ),
                    crispy.Div(
                        twbscrispy.InlineField(
                            'location_types',
                            data_bind='value: location_types.value',
                            placeholder=_("Select organization levels(s)")
                        ),
                        data_bind="visible: restrict_location_types() === 'Y'",
                        css_class='col-sm-6',
                    ),
                    data_bind="visible: include_descendant_locations()",
                ),
                data_bind="visible: recipientTypeSelected('%s')" % ScheduleInstance.RECIPIENT_TYPE_LOCATION,
            ),
            crispy.Div(
                crispy.Field(
                    'case_group_recipients',
                    data_bind='value: case_group_recipients.value',
                    placeholder=_("Select case group(s)")
                ),
                data_bind="visible: recipientTypeSelected('%s')" % ScheduleInstance.RECIPIENT_TYPE_CASE_GROUP,
            ),
        ]

    @property
    def display_utc_timezone_option(self):
        """
        See comment under Schedule.use_utc_as_default_timezone.
        use_utc_as_default_timezone is only set to True on reminders migrated
        from the old framework that needed it to be set to True. We don't
        encourage using this option for new reminders so it's only visible
        for those reminders that have it set to True. It is possible to edit
        an old reminder and disable the option, after which it will be hidden
        and won't be allowed to be enabled again.
        """
        return self.initial_schedule and self.initial_schedule.use_utc_as_default_timezone

    def get_advanced_layout_fields(self):
        result = [
            crispy.Div(
                crispy.Field('use_utc_as_default_timezone'),
                data_bind='visible: %s' % ('true' if self.display_utc_timezone_option else 'false'),
            ),
            crispy.Field('default_language_code'),
        ]

        if self.use_advanced_user_data_filter:
            result.extend([
                hqcrispy.B3MultiField(
                    _("Filter user recipients"),
                    crispy.Div(
                        twbscrispy.InlineField(
                            'use_user_data_filter',
                            data_bind='value: use_user_data_filter',
                        ),
                        get_system_admin_label("visible: use_user_data_filter() === '%s'" % self.JSON),
                        css_class='col-sm-4',
                    ),
                ),
                crispy.Div(
                    crispy.Field('user_data_property_name'),
                    crispy.Field('user_data_property_value'),
                    data_bind="visible: use_user_data_filter() !== 'N'",
                ),
            ])

        return result

    def get_advanced_survey_layout_fields(self):
        return [
            crispy.Field(
                'submit_partially_completed_forms',
                data_bind='checked: submit_partially_completed_forms',
            ),
            crispy.Div(
                crispy.Field(
                    'include_case_updates_in_partial_submissions',
                ),
                data_bind='visible: submit_partially_completed_forms()',
            )
        ]

    @cached_property
    def language_list(self):
        sms_translations = get_or_create_sms_translations(self.domain)
        result = sms_translations.langs     # maintain order set on languages config page

        # add any languages present in alert but deleted from languages config page
        if self.initial_schedule:
            initial_langs = self.initial_schedule.memoized_language_set
            initial_langs.discard('*')
            result += list(self.initial_schedule.memoized_language_set - set(result))

        return result

    def html_message_template(self):
        if RICH_TEXT_EMAILS.enabled(self.domain):
            return escape(render_to_string('scheduling/partials/rich_text_email_template.html'))
        else:
            return ''

    @property
    def use_case(self):
        raise NotImplementedError()

    @property
    def current_values(self):
        values = {}
        for field_name in self.fields.keys():
            values[field_name] = self[field_name].value()
        values['standalone_content_form'] = self.standalone_content_form.current_values
        values['custom_event_formset'] = [form.current_values for form in self.custom_event_formset]
        values['editing_custom_immediate_schedule'] = self.editing_custom_immediate_schedule
        values['use_case'] = self.use_case
        return values

    @property
    def current_select2_user_recipients(self):
        value = self['user_recipients'].value()
        if not value:
            return []

        result = []
        for user_id in value:
            user_id = user_id.strip()
            user = CommCareUser.get_by_user_id(user_id, domain=self.domain)
            if user and not user.is_deleted():
                result.append({"id": user_id, "text": user.raw_username})
            else:
                # Always add it here because, separately, the id still shows up in the
                # field's value and it will raise a ValidationError. By adding it here
                # it allows the user to remove it and fix the ValidationError.
                result.append({"id": user_id, "text": _("(not found)")})

        return result

    @property
    def current_select2_user_group_recipients(self):
        value = self['user_group_recipients'].value()
        if not value:
            return []

        result = []
        for group_id in value:
            group_id = group_id.strip()
            group = Group.get(group_id)
            if group.doc_type != 'Group' or group.domain != self.domain:
                result.append({"id": group_id, "text": _("(not found)")})
            else:
                result.append({"id": group_id, "text": group.name})

        return result

    @property
    def current_select2_user_organization_recipients(self):
        value = self['user_organization_recipients'].value()
        if not value:
            return []

        result = []
        for location_id in value:
            location_id = location_id.strip()
            try:
                location = SQLLocation.objects.get(domain=self.domain, location_id=location_id, is_archived=False)
            except SQLLocation.DoesNotExist:
                result.append({"id": location_id, "text": _("(not found)")})
            else:
                result.append({"id": location_id, "text": location.name})

        return result

    @property
    def current_select2_location_types(self):
        value = self['location_types'].value()
        if not value:
            return []

        result = []
        for location_type_id in value:
            location_type_id = location_type_id.strip()
            try:
                location_type = LocationType.objects.get(domain=self.domain, pk=location_type_id)
            except LocationType.DoesNotExist:
                result.append({"id": location_type_id, "text": _("(not found)")})
            else:
                result.append({"id": location_type_id, "text": location_type.name})

        return result

    @property
    def current_select2_case_group_recipients(self):
        value = self['case_group_recipients'].value()
        if not value:
            return []

        result = []
        for case_group_id in value:
            case_group_id = case_group_id.strip()
            case_group = CommCareCaseGroup.get(case_group_id)
            if case_group.doc_type != 'CommCareCaseGroup' or case_group.domain != self.domain:
                result.append({"id": case_group_id, "text": _("(not found)")})
            else:
                result.append({"id": case_group_id, "text": case_group.name})

        return result

    @property
    def current_visit_scheduler_form(self):
        """
        Only used in the ConditionalAlertScheduleForm
        """
        return {}

    @property
    def uses_sms_survey(self):
        return self.cleaned_data.get('content') == self.CONTENT_SMS_SURVEY

    def clean_active(self):
        return self.cleaned_data.get('active') == 'Y'

    def clean_user_recipients(self):
        if ScheduleInstance.RECIPIENT_TYPE_MOBILE_WORKER not in self.cleaned_data.get('recipient_types', []):
            return []

        data = self.cleaned_data['user_recipients']

        if not data:
            raise ValidationError(_("Please specify the user(s) or deselect users as recipients"))

        for user_id in data:
            user = CommCareUser.get_by_user_id(user_id, domain=self.domain)
            if not user or user.is_deleted():
                raise ValidationError(
                    _("One or more users were unexpectedly not found. Please select user(s) again.")
                )

        return data

    def clean_user_group_recipients(self):
        if ScheduleInstance.RECIPIENT_TYPE_USER_GROUP not in self.cleaned_data.get('recipient_types', []):
            return []

        data = self.cleaned_data['user_group_recipients']

        if not data:
            raise ValidationError(_("Please specify the groups(s) or deselect user groups as recipients"))

        not_found_error = ValidationError(
            _("One or more user groups were unexpectedly not found. Please select group(s) again.")
        )

        for group_id in data:
            try:
                group = Group.get(group_id)
            except ResourceNotFound:
                raise not_found_error

            if group.doc_type != 'Group':
                raise not_found_error

            if group.domain != self.domain:
                raise not_found_error

        return data

    def clean_user_organization_recipients(self):
        if ScheduleInstance.RECIPIENT_TYPE_LOCATION not in self.cleaned_data.get('recipient_types', []):
            return []

        data = self.cleaned_data['user_organization_recipients']

        if not data:
            raise ValidationError(
                _("Please specify the organization(s) or deselect user organizations as recipients")
            )

        for location_id in data:
            try:
                SQLLocation.objects.get(domain=self.domain, location_id=location_id, is_archived=False)
            except SQLLocation.DoesNotExist:
                raise ValidationError(
                    _("One or more user organizations were unexpectedly not found. "
                      "Please select organization(s) again.")
                )

        return data

    def clean_location_types(self):
        if ScheduleInstance.RECIPIENT_TYPE_LOCATION not in self.cleaned_data.get('recipient_types', []):
            return []

        if not self.cleaned_data.get('include_descendant_locations'):
            return []

        if self.cleaned_data.get('restrict_location_types') != 'Y':
            return []

        data = self.cleaned_data['location_types']

        if not data:
            raise ValidationError(
                _("Please specify the organization level(s) or choose to send to all organization levels")
            )

        result = []

        for location_type_id in data:
            try:
                location_type_id = int(location_type_id)
            except (TypeError, ValueError):
                raise ValidationError(_("An error occurred. Please try again"))

            try:
                LocationType.objects.get(domain=self.domain, pk=location_type_id)
            except LocationType.DoesNotExist:
                raise ValidationError(
                    _("One or more user organization levels were unexpectedly not found. "
                      "Please select organization level(s) again.")
                )

            result.append(location_type_id)

        return result

    def clean_case_group_recipients(self):
        if ScheduleInstance.RECIPIENT_TYPE_CASE_GROUP not in self.cleaned_data.get('recipient_types', []):
            return []

        data = self.cleaned_data['case_group_recipients']

        if not data:
            raise ValidationError(
                _("Please specify the case groups(s) or deselect case groups as recipients")
            )

        not_found_error = ValidationError(
            _("One or more case groups were unexpectedly not found. Please select group(s) again.")
        )

        for case_group_id in data:
            try:
                case_group = CommCareCaseGroup.get(case_group_id)
            except ResourceNotFound:
                raise not_found_error

            if case_group.doc_type != 'CommCareCaseGroup':
                raise not_found_error

            if case_group.domain != self.domain:
                raise not_found_error

        return data

    def clean_weekdays(self):
        if self.cleaned_data.get('send_frequency') != self.SEND_WEEKLY:
            return None

        weeekdays = self.cleaned_data.get('weekdays')
        if not weeekdays:
            raise ValidationError(_("Please select the applicable day(s) of the week."))

        return [int(i) for i in weeekdays]

    def clean_days_of_month(self):
        if self.cleaned_data.get('send_frequency') != self.SEND_MONTHLY:
            return None

        days_of_month = self.cleaned_data.get('days_of_month')
        if not days_of_month:
            raise ValidationError(_("Please select the applicable day(s) of the month."))

        return [int(i) for i in days_of_month]

    def cleaned_data_uses_custom_event_definitions(self):
        return self.cleaned_data.get('send_frequency') in (self.SEND_CUSTOM_DAILY, self.SEND_CUSTOM_IMMEDIATE)

    def cleaned_data_uses_alert_schedule(self):
        return self.cleaned_data.get('send_frequency') in (self.SEND_IMMEDIATELY, self.SEND_CUSTOM_IMMEDIATE)

    def cleaned_data_uses_timed_schedule(self):
        return self.cleaned_data.get('send_frequency') in (
            self.SEND_DAILY,
            self.SEND_WEEKLY,
            self.SEND_MONTHLY,
            self.SEND_CUSTOM_DAILY,
        )

    def clean_send_time(self):
        if (
            self.cleaned_data_uses_custom_event_definitions()
            or self.cleaned_data_uses_alert_schedule()
            or self.cleaned_data.get('send_time_type') not in [
                TimedSchedule.EVENT_SPECIFIC_TIME, TimedSchedule.EVENT_RANDOM_TIME
            ]
        ):
            return None

        return validate_time(self.cleaned_data.get('send_time'))

    def clean_window_length(self):
        if (
            self.cleaned_data_uses_custom_event_definitions()
            or self.cleaned_data_uses_alert_schedule()
            or self.cleaned_data.get('send_time_type') != TimedSchedule.EVENT_RANDOM_TIME
        ):
            return None

        value = self.cleaned_data.get('window_length')
        if value is None:
            raise ValidationError(_("This field is required."))

        return value

    def clean_start_date(self):
        if self.cleaned_data_uses_alert_schedule():
            return None

        return validate_date(self.cleaned_data.get('start_date'))

    def clean_repeat(self):
        if self.cleaned_data_uses_alert_schedule():
            return None

        repeat = self.cleaned_data.get('repeat')
        if not repeat:
            raise ValidationError(_("This field is required"))

        return repeat

    def clean_repeat_every(self):
        if (
            self.cleaned_data_uses_alert_schedule()
            or self.cleaned_data.get('repeat') != self.REPEAT_EVERY_N
        ):
            return None

        return validate_int(self.cleaned_data.get('repeat_every'), 2)

    def clean_stop_type(self):
        if (
            self.cleaned_data_uses_alert_schedule()
            or self.cleaned_data.get('repeat') == self.REPEAT_NO
        ):
            return None

        stop_type = self.cleaned_data.get('stop_type')
        if not stop_type:
            raise ValidationError(_("This field is required"))

        return stop_type

    def clean_occurrences(self):
        if (
            self.cleaned_data_uses_alert_schedule()
            or self.cleaned_data.get('repeat') == self.REPEAT_NO
            or self.cleaned_data.get('stop_type') != self.STOP_AFTER_OCCURRENCES
        ):
            return None

        return validate_int(self.cleaned_data.get('occurrences'), 2)

    def clean_user_data_property_name(self):
        if self.cleaned_data.get('use_user_data_filter') == self.NO:
            return None

        value = self.cleaned_data.get('user_data_property_name')
        if not value:
            raise ValidationError(_("This field is required."))

        return value

    def clean_user_data_property_value(self):
        use_user_data_filter = self.cleaned_data.get('use_user_data_filter')
        if use_user_data_filter == self.NO:
            return None

        value = self.cleaned_data.get('user_data_property_value')
        if not value:
            raise ValidationError(_("This field is required."))

        if use_user_data_filter == self.JSON:
            err = _("Invalid JSON value. Expected a list of strings.")
            try:
                value = json.loads(value)
            except Exception:
                raise ValidationError(err)
            if (not isinstance(value, list) or not value
                    or any(not isinstance(v, str) for v in value)):
                raise ValidationError(err)
        else:
            value = [value]

        return value

    def distill_recipients(self):
        form_data = self.cleaned_data
        return (
            [(ScheduleInstance.RECIPIENT_TYPE_MOBILE_WORKER, user_id)
             for user_id in form_data['user_recipients']]
            + [(ScheduleInstance.RECIPIENT_TYPE_USER_GROUP, group_id)
               for group_id in form_data['user_group_recipients']]
            + [(ScheduleInstance.RECIPIENT_TYPE_LOCATION, location_id)
               for location_id in form_data['user_organization_recipients']]
            + [(ScheduleInstance.RECIPIENT_TYPE_CASE_GROUP, case_group_id)
               for case_group_id in form_data['case_group_recipients']]
        )

    def distill_total_iterations(self):
        form_data = self.cleaned_data
        if form_data['repeat'] == self.REPEAT_NO:
            return 1
        elif form_data['stop_type'] == self.STOP_NEVER:
            return TimedSchedule.REPEAT_INDEFINITELY

        return form_data['occurrences']

    def distill_repeat_every(self):
        if self.cleaned_data['repeat'] == self.REPEAT_EVERY_N:
            return self.cleaned_data['repeat_every']

        return 1

    def distill_default_language_code(self):
        value = self.cleaned_data['default_language_code']
        if value == self.LANGUAGE_PROJECT_DEFAULT:
            return None
        else:
            return value

    def distill_extra_scheduling_options(self):
        form_data = self.cleaned_data
        return {
            'active': form_data['active'],
            'default_language_code': self.distill_default_language_code(),
            'include_descendant_locations': (
                ScheduleInstance.RECIPIENT_TYPE_LOCATION in form_data['recipient_types']
                and form_data['include_descendant_locations']
            ),
            'location_type_filter': form_data['location_types'],
            'use_utc_as_default_timezone': form_data['use_utc_as_default_timezone'],
            'user_data_filter': self.distill_user_data_filter(),
        }

    def distill_user_data_filter(self):
        if self.cleaned_data['use_user_data_filter'] == self.NO:
            return {}

        name = self.cleaned_data['user_data_property_name']
        value = self.cleaned_data['user_data_property_value']
        return {name: value}

    def distill_start_offset(self):
        raise NotImplementedError()

    def distill_start_day_of_week(self):
        raise NotImplementedError()

    def distill_model_timed_event(self):
        if self.cleaned_data_uses_custom_event_definitions():
            raise ValueError("Cannot use this method with custom event definitions")

        event_type = self.cleaned_data['send_time_type']
        if event_type == TimedSchedule.EVENT_SPECIFIC_TIME:
            return TimedEvent(
                time=self.cleaned_data['send_time'],
            )
        elif event_type == TimedSchedule.EVENT_RANDOM_TIME:
            return RandomTimedEvent(
                time=self.cleaned_data['send_time'],
                window_length=self.cleaned_data['window_length'],
            )
        else:
            raise ValueError("Unexpected send_time_type: %s" % event_type)

    def save_immediate_schedule(self):
        content = self.standalone_content_form.distill_content()
        extra_scheduling_options = self.distill_extra_scheduling_options()

        if self.initial_schedule:
            schedule = self.initial_schedule
            AlertSchedule.assert_is(schedule)
            schedule.set_simple_alert(content, extra_options=extra_scheduling_options)
        else:
            schedule = AlertSchedule.create_simple_alert(self.domain, content,
                extra_options=extra_scheduling_options)

        return schedule

    def save_daily_schedule(self):
        repeat_every = self.distill_repeat_every()
        total_iterations = self.distill_total_iterations()
        content = self.standalone_content_form.distill_content()
        extra_scheduling_options = self.distill_extra_scheduling_options()

        if self.initial_schedule:
            schedule = self.initial_schedule
            TimedSchedule.assert_is(schedule)
            schedule.set_simple_daily_schedule(
                self.distill_model_timed_event(),
                content,
                total_iterations=total_iterations,
                start_offset=self.distill_start_offset(),
                extra_options=extra_scheduling_options,
                repeat_every=repeat_every,
            )
        else:
            schedule = TimedSchedule.create_simple_daily_schedule(
                self.domain,
                self.distill_model_timed_event(),
                content,
                total_iterations=total_iterations,
                start_offset=self.distill_start_offset(),
                extra_options=extra_scheduling_options,
                repeat_every=repeat_every,
            )

        return schedule

    def save_weekly_schedule(self):
        form_data = self.cleaned_data
        repeat_every = self.distill_repeat_every()
        total_iterations = self.distill_total_iterations()
        content = self.standalone_content_form.distill_content()
        extra_scheduling_options = self.distill_extra_scheduling_options()

        if self.initial_schedule:
            schedule = self.initial_schedule
            TimedSchedule.assert_is(schedule)
            schedule.set_simple_weekly_schedule(
                self.distill_model_timed_event(),
                content,
                form_data['weekdays'],
                self.distill_start_day_of_week(),
                total_iterations=total_iterations,
                extra_options=extra_scheduling_options,
                repeat_every=repeat_every,
            )
        else:
            schedule = TimedSchedule.create_simple_weekly_schedule(
                self.domain,
                self.distill_model_timed_event(),
                content,
                form_data['weekdays'],
                self.distill_start_day_of_week(),
                total_iterations=total_iterations,
                extra_options=extra_scheduling_options,
                repeat_every=repeat_every,
            )

        return schedule

    def save_monthly_schedule(self):
        form_data = self.cleaned_data
        repeat_every = self.distill_repeat_every()
        total_iterations = self.distill_total_iterations()
        content = self.standalone_content_form.distill_content()
        extra_scheduling_options = self.distill_extra_scheduling_options()

        positive_days = [day for day in form_data['days_of_month'] if day > 0]
        negative_days = [day for day in form_data['days_of_month'] if day < 0]
        sorted_days_of_month = sorted(positive_days) + sorted(negative_days)

        if self.initial_schedule:
            schedule = self.initial_schedule
            TimedSchedule.assert_is(schedule)
            schedule.set_simple_monthly_schedule(
                self.distill_model_timed_event(),
                sorted_days_of_month,
                content,
                total_iterations=total_iterations,
                extra_options=extra_scheduling_options,
                repeat_every=repeat_every,
            )
        else:
            schedule = TimedSchedule.create_simple_monthly_schedule(
                self.domain,
                self.distill_model_timed_event(),
                sorted_days_of_month,
                content,
                total_iterations=total_iterations,
                extra_options=extra_scheduling_options,
                repeat_every=repeat_every,
            )

        return schedule

    def save_custom_daily_schedule(self):
        event_and_content_objects = [
            (form.distill_event(), form.distill_content())
            for form in self.custom_event_formset.non_deleted_forms
        ]
        total_iterations = self.distill_total_iterations()

        if total_iterations == 1:
            # Just give a default value which is the minimum value
            repeat_every = event_and_content_objects[-1][0].day + 1
        else:
            repeat_every = self.distill_repeat_every()

        extra_scheduling_options = self.distill_extra_scheduling_options()

        if self.initial_schedule:
            schedule = self.initial_schedule
            TimedSchedule.assert_is(schedule)
            schedule.set_custom_daily_schedule(
                event_and_content_objects,
                total_iterations=total_iterations,
                start_offset=self.distill_start_offset(),
                extra_options=extra_scheduling_options,
                repeat_every=repeat_every,
            )
        else:
            schedule = TimedSchedule.create_custom_daily_schedule(
                self.domain,
                event_and_content_objects,
                total_iterations=total_iterations,
                start_offset=self.distill_start_offset(),
                extra_options=extra_scheduling_options,
                repeat_every=repeat_every,
            )

        return schedule

    def save_custom_immediate_schedule(self):
        event_and_content_objects = [
            (form.distill_event(), form.distill_content())
            for form in self.custom_event_formset.non_deleted_forms
        ]
        extra_scheduling_options = self.distill_extra_scheduling_options()

        if self.initial_schedule:
            schedule = self.initial_schedule
            AlertSchedule.assert_is(schedule)
            schedule.set_custom_alert(event_and_content_objects, extra_options=extra_scheduling_options)
        else:
            schedule = AlertSchedule.create_custom_alert(self.domain, event_and_content_objects,
                extra_options=extra_scheduling_options)

        return schedule

    def save_schedule(self):
        send_frequency = self.cleaned_data['send_frequency']
        return {
            self.SEND_IMMEDIATELY: self.save_immediate_schedule,
            self.SEND_DAILY: self.save_daily_schedule,
            self.SEND_WEEKLY: self.save_weekly_schedule,
            self.SEND_MONTHLY: self.save_monthly_schedule,
            self.SEND_CUSTOM_DAILY: self.save_custom_daily_schedule,
            self.SEND_CUSTOM_IMMEDIATE: self.save_custom_immediate_schedule,
        }[send_frequency]()


class BroadcastForm(ScheduleForm):

    use_case = 'broadcast'

    schedule_name = CharField(
        required=True,
        label=gettext_lazy("Broadcast Name"),
        max_length=1000,
    )

    def __init__(self, domain, schedule, can_use_sms_surveys, broadcast, *args, **kwargs):
        self.initial_broadcast = broadcast
        super(BroadcastForm, self).__init__(domain, schedule, can_use_sms_surveys, *args, **kwargs)

    def clean_active(self):
        active = super(BroadcastForm, self).clean_active()

        if self.cleaned_data.get('send_frequency') == self.SEND_IMMEDIATELY and not active:
            raise ValidationError(_("You cannot create an immediate broadcast which is inactive."))

        return active

    def get_after_content_layout_fields(self):
        result = super(BroadcastForm, self).get_after_content_layout_fields()
        result.append(
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Save"),
                    data_bind='text: saveBroadcastText()',
                    css_class='btn-primary',
                    type='submit',
                ),
            )
        )
        return result

    def get_start_date_layout_fields(self):
        return [
            hqcrispy.B3MultiField(
                _("Start"),
                crispy.Div(
                    twbscrispy.InlineField(
                        'start_date',
                        data_bind='value: start_date',
                    ),
                    css_class='col-sm-4',
                ),
                data_bind='visible: usesTimedSchedule()',
            ),
        ]

    def get_scheduling_layout_fields(self):
        result = [
            crispy.Field('schedule_name'),
        ]
        result.extend(super(BroadcastForm, self).get_scheduling_layout_fields())
        return result

    def compute_initial(self, domain):
        result = super(BroadcastForm, self).compute_initial(self.domain)
        if self.initial_broadcast:
            result['schedule_name'] = self.initial_broadcast.name
            self.add_initial_recipients(self.initial_broadcast.recipients, result)
            if isinstance(self.initial_broadcast, ScheduledBroadcast):
                result['start_date'] = self.initial_broadcast.start_date.strftime('%Y-%m-%d')

        return result

    def distill_start_offset(self):
        return 0

    def distill_start_day_of_week(self):
        if self.cleaned_data['send_frequency'] != self.SEND_WEEKLY:
            return TimedSchedule.ANY_DAY

        return self.cleaned_data['start_date'].weekday()

    def save_immediate_broadcast(self, schedule):
        form_data = self.cleaned_data
        recipients = self.distill_recipients()

        if self.initial_broadcast:
            raise ImmediateMessageEditAttempt("Cannot edit an ImmediateBroadcast")

        return ImmediateBroadcast.objects.create(
            domain=self.domain,
            name=form_data['schedule_name'],
            schedule=schedule,
            recipients=recipients,
        )

    def save_scheduled_broadcast(self, schedule):
        form_data = self.cleaned_data
        recipients = self.distill_recipients()

        if self.initial_broadcast:
            broadcast = self.initial_broadcast
            if not isinstance(broadcast, ScheduledBroadcast):
                raise TypeError("Expected ScheduledBroadcast")
        else:
            broadcast = ScheduledBroadcast(
                domain=self.domain,
                schedule=schedule,
            )

        broadcast.name = form_data['schedule_name']
        broadcast.start_date = form_data['start_date']
        broadcast.recipients = recipients
        broadcast.save()
        return broadcast

    def save_broadcast_and_schedule(self):
        with transaction.atomic():
            schedule = self.save_schedule()

            send_frequency = self.cleaned_data['send_frequency']
            if send_frequency == self.SEND_CUSTOM_IMMEDIATE:
                raise ValueError(
                    "Did not expect to see custom immediate schedule as a value for send_frequency "
                    "in a broadcast. Check that send_frequency choices are being restricted properly."
                )

            broadcast = {
                self.SEND_IMMEDIATELY: self.save_immediate_broadcast,
                self.SEND_DAILY: self.save_scheduled_broadcast,
                self.SEND_WEEKLY: self.save_scheduled_broadcast,
                self.SEND_MONTHLY: self.save_scheduled_broadcast,
                self.SEND_CUSTOM_DAILY: self.save_scheduled_broadcast,
            }[send_frequency](schedule)

        return (broadcast, schedule)


class ConditionalAlertScheduleForm(ScheduleForm):
    START_DATE_RULE_TRIGGER = 'RULE_TRIGGER'
    START_DATE_CASE_PROPERTY = 'CASE_PROPERTY'
    START_DATE_SPECIFIC_DATE = 'SPECIFIC_DATE'
    START_DATE_FROM_VISIT_SCHEDULER = 'VISIT_SCHEDULER'

    START_OFFSET_ZERO = 'ZERO'
    START_OFFSET_NEGATIVE = 'NEGATIVE'
    START_OFFSET_POSITIVE = 'POSITIVE'

    use_case = 'conditional_alert'

    FCM_SUPPORTED_RECIPIENT_TYPES = [
        ScheduleInstance.RECIPIENT_TYPE_MOBILE_WORKER,
        ScheduleInstance.RECIPIENT_TYPE_LOCATION,
        ScheduleInstance.RECIPIENT_TYPE_USER_GROUP,
        CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_OWNER,
        CaseScheduleInstanceMixin.RECIPIENT_TYPE_LAST_SUBMITTING_USER,
        CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_PROPERTY_USER,
        CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM,
    ]

    # start_date is defined on the superclass but cleaning it in this subclass
    # depends on start_date_type, which depends on send_frequency
    field_order = [
        'send_frequency',
        'start_date_type',
        'start_date',
    ]

    start_date_type = ChoiceField(
        required=False,
        choices=(
            (START_DATE_RULE_TRIGGER, gettext_lazy("The first available time after the rule is satisfied")),
            (START_DATE_CASE_PROPERTY, gettext_lazy("The date from case property")),
            (START_DATE_SPECIFIC_DATE, gettext_lazy("A specific date")),
        )
    )

    start_date_case_property = TrimmedCharField(
        label='',
        required=False,
    )

    start_offset_type = ChoiceField(
        required=False,
        choices=(
            (START_OFFSET_ZERO, gettext_lazy("Exactly on the start date")),
            (START_OFFSET_NEGATIVE, gettext_lazy("Before the start date by")),
            (START_OFFSET_POSITIVE, gettext_lazy("After the start date by")),
        )
    )

    start_offset = IntegerField(
        label='',
        required=False,
        min_value=1,
    )

    start_day_of_week = ChoiceField(
        required=False,
        choices=(
            ('6', gettext_lazy('The first Sunday that occurs on or after the start date')),
            ('0', gettext_lazy('The first Monday that occurs on or after the start date')),
            ('1', gettext_lazy('The first Tuesday that occurs on or after the start date')),
            ('2', gettext_lazy('The first Wednesday that occurs on or after the start date')),
            ('3', gettext_lazy('The first Thursday that occurs on or after the start date')),
            ('4', gettext_lazy('The first Friday that occurs on or after the start date')),
            ('5', gettext_lazy('The first Saturday that occurs on or after the start date')),
        ),
    )

    custom_recipient = ChoiceField(
        required=False,
        choices=(
            [('', '')]
            + [(k, v[1]) for k, v in settings.AVAILABLE_CUSTOM_SCHEDULING_RECIPIENTS.items()]
        )
    )

    username_case_property = CharField(
        required=False,
    )

    email_case_property = CharField(
        required=False,
    )

    reset_case_property_enabled = ChoiceField(
        required=True,
        choices=(
            (ScheduleForm.NO, gettext_lazy("Disabled")),
            (ScheduleForm.YES, gettext_lazy("Restart schedule when this case property takes any new value: ")),
        ),
    )

    reset_case_property_name = TrimmedCharField(
        label='',
        required=False,
    )

    send_time_case_property_name = TrimmedCharField(
        label='',
        required=False,
    )

    # The app id and form unique id of a visit scheduler form, separated by '|'
    visit_scheduler_app_and_form_unique_id = CharField(
        label=gettext_lazy("Scheduler: Form"),
        required=False,
        widget=Select(choices=[]),
    )

    visit_number = IntegerField(
        label='',
        required=False,
        min_value=1,
    )

    visit_window_position = ChoiceField(
        label=gettext_lazy("Scheduler: Use"),
        required=False,
        choices=(
            (VISIT_WINDOW_START, gettext_lazy("the first date in the visit window")),
            (VISIT_WINDOW_DUE_DATE, gettext_lazy("the due date of the visit")),
            (VISIT_WINDOW_END, gettext_lazy("the last date in the visit window")),
        ),
    )

    capture_custom_metadata_item = ChoiceField(
        label='',
        choices=(
            (ScheduleForm.NO, gettext_lazy("No")),
            (ScheduleForm.YES, gettext_lazy("Yes")),
        ),
        required=False,
    )

    custom_metadata_item_name = TrimmedCharField(
        label=gettext_lazy("Custom Data: Name"),
        required=False,
    )

    custom_metadata_item_value = TrimmedCharField(
        label=gettext_lazy("Custom Data: Value"),
        required=False,
    )

    stop_date_case_property_enabled = ChoiceField(
        required=True,
        choices=(
            (ScheduleForm.NO, gettext_lazy("No")),
            (ScheduleForm.YES, gettext_lazy("Yes")),
        ),
    )

    stop_date_case_property_name = TrimmedCharField(
        label='',
        required=False,
    )

    allow_custom_immediate_schedule = True

    def __init__(self, domain, schedule, can_use_sms_surveys, rule, criteria_form, *args, **kwargs):
        self.initial_rule = rule
        self.criteria_form = criteria_form
        super(ConditionalAlertScheduleForm, self).__init__(domain, schedule, can_use_sms_surveys, *args, **kwargs)
        if self.initial_rule:
            self.set_read_only_fields_during_editing()
        self.update_recipient_types_choices()
        self.update_send_time_type_choices()
        self.update_start_date_type_choices()

    def get_extra_timing_fields(self):
        return [
            crispy.Div(
                twbscrispy.InlineField('send_time_case_property_name'),
                data_bind="visible: send_time_type() === '%s'" % TimedSchedule.EVENT_CASE_PROPERTY_TIME,
                css_class='col-sm-6',
            ),
        ]

    def add_additional_content_types(self):
        super(ConditionalAlertScheduleForm, self).add_additional_content_types()

        if (
            self.is_system_admin
            or self.initial.get('content') == self.CONTENT_CUSTOM_SMS
        ):
            self.fields['content'].choices += [
                (self.CONTENT_CUSTOM_SMS, _("Custom SMS")),
            ]

        if (
            self.initial.get('content') == self.CONTENT_FCM_NOTIFICATION
            or (FCM_NOTIFICATION.enabled(self.domain) and settings.FCM_CREDS)
        ):
            self.fields['content'].choices += [
                (self.CONTENT_FCM_NOTIFICATION, _("Push Notification"))
            ]

    @property
    def current_visit_scheduler_form(self):
        value = self['visit_scheduler_app_and_form_unique_id'].value()
        if not value:
            return {}

        app_id, form_unique_id = split_combined_id(value)
        try:
            form, app = self.get_latest_released_form_and_app(app_id, form_unique_id)
        except Exception:
            return {}

        return {'id': value, 'text': form.full_path_name}

    @property
    def scheduling_fieldset_legend(self):
        return ''

    def set_read_only_fields_during_editing(self):
        # Django also handles keeping the field's value to its initial value no matter what is posted
        # https://docs.djangoproject.com/en/1.11/ref/forms/fields/#disabled

        # Don't allow the reset_case_property_name to change values after being initially set.
        # The framework doesn't account for this option being enabled, disabled, or changing
        # after being initially set.
        self.fields['reset_case_property_enabled'].disabled = True
        self.fields['reset_case_property_name'].disabled = True

    @cached_property
    def requires_system_admin_to_edit(self):
        return (
            CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM in self.initial.get('recipient_types', [])
            or self.initial.get('content') == self.CONTENT_CUSTOM_SMS
            or self.initial.get('start_date_type') == self.START_DATE_FROM_VISIT_SCHEDULER
            or self.initial.get('capture_custom_metadata_item') == self.YES
        )

    @cached_property
    def requires_system_admin_to_save(self):
        return (
            CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM in self.cleaned_data['recipient_types']
            or self.cleaned_data['content'] == self.CONTENT_CUSTOM_SMS
            or self.cleaned_data['start_date_type'] == self.START_DATE_FROM_VISIT_SCHEDULER
            or self.cleaned_data['capture_custom_metadata_item'] == self.YES
        )

    def update_send_time_type_choices(self):
        self.fields['send_time_type'].choices += [
            (TimedSchedule.EVENT_CASE_PROPERTY_TIME, _("The time from case property")),
        ]

    def update_recipient_types_choices(self):
        new_choices = [
            (CaseScheduleInstanceMixin.RECIPIENT_TYPE_SELF, _("The Case")),
            (CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_OWNER, _("The Case's Owner")),
            (CaseScheduleInstanceMixin.RECIPIENT_TYPE_LAST_SUBMITTING_USER, _("The Case's Last Submitting User")),
            (CaseScheduleInstanceMixin.RECIPIENT_TYPE_PARENT_CASE, _("The Case's Parent Case")),
            (CaseScheduleInstanceMixin.RECIPIENT_TYPE_ALL_CHILD_CASES, _("The Case's Child Cases")),
            (CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_PROPERTY_USER, _("User Specified via Case Property")),
            (CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_PROPERTY_EMAIL, _("Email Specified via Case Property")),
        ]
        new_choices.extend(self.fields['recipient_types'].choices)

        if (
            self.is_system_admin
            or CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM in self.initial.get('recipient_types', [])
        ):
            new_choices.extend([
                (CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM, _("Custom Recipient")),
            ])

        self.fields['recipient_types'].choices = new_choices

    def update_start_date_type_choices(self):
        if (
            self.is_system_admin
            or self.initial.get('start_date_type') == self.START_DATE_FROM_VISIT_SCHEDULER
        ):
            self.fields['start_date_type'].choices += [
                (self.START_DATE_FROM_VISIT_SCHEDULER, _("A date from a visit scheduler")),
            ]

    def add_initial_for_send_time(self, initial):
        if initial['send_frequency'] not in (self.SEND_DAILY, self.SEND_WEEKLY, self.SEND_MONTHLY):
            return

        if self.initial_schedule.event_type == TimedSchedule.EVENT_CASE_PROPERTY_TIME:
            initial['send_time_case_property_name'] = \
                self.initial_schedule.memoized_events[0].case_property_name
        else:
            super(ConditionalAlertScheduleForm, self).add_initial_for_send_time(initial)

    def add_initial_recipients(self, recipients, initial):
        super(ConditionalAlertScheduleForm, self).add_initial_recipients(recipients, initial)

        for recipient_type, recipient_id in recipients:
            if recipient_type == CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM:
                initial['custom_recipient'] = recipient_id
            if recipient_type == CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_PROPERTY_USER:
                initial['username_case_property'] = recipient_id
            if recipient_type == CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_PROPERTY_EMAIL:
                initial['email_case_property'] = recipient_id

    def add_initial_for_custom_metadata(self, result):
        if (
            isinstance(self.initial_schedule.custom_metadata, dict)
            and len(self.initial_schedule.custom_metadata) > 0
        ):
            result['capture_custom_metadata_item'] = self.YES
            for name, value in self.initial_schedule.custom_metadata.items():
                result['custom_metadata_item_name'] = name
                result['custom_metadata_item_value'] = value
                # We only capture one item right now, but the framework allows
                # capturing any number of name, value pairs
                break

    def compute_initial(self, domain):
        result = super(ConditionalAlertScheduleForm, self).compute_initial(self.domain)

        if self.initial_rule:
            action_definition = self.initial_rule.memoized_actions[0].definition
            self.add_initial_recipients(action_definition.recipients, result)
            if action_definition.reset_case_property_name:
                result['reset_case_property_enabled'] = self.YES
                result['reset_case_property_name'] = action_definition.reset_case_property_name
            else:
                result['reset_case_property_enabled'] = self.NO

            scheduler_module_info = action_definition.get_scheduler_module_info()
            if action_definition.start_date_case_property:
                result['start_date_type'] = self.START_DATE_CASE_PROPERTY
                result['start_date_case_property'] = action_definition.start_date_case_property
            elif action_definition.specific_start_date:
                result['start_date_type'] = self.START_DATE_SPECIFIC_DATE
                result['start_date'] = action_definition.specific_start_date
            elif scheduler_module_info.enabled:
                result['visit_scheduler_app_and_form_unique_id'] = get_combined_id(
                    scheduler_module_info.app_id,
                    scheduler_module_info.form_unique_id
                )
                result['start_date_type'] = self.START_DATE_FROM_VISIT_SCHEDULER

                # Convert to 1-based index for display as in the form builder
                result['visit_number'] = scheduler_module_info.visit_number + 1
                result['visit_window_position'] = scheduler_module_info.window_position
            else:
                result['start_date_type'] = self.START_DATE_RULE_TRIGGER

        if self.initial_schedule:
            schedule = self.initial_schedule
            if (
                isinstance(schedule, TimedSchedule)
                and result.get('start_date_type') != self.START_DATE_SPECIFIC_DATE
            ):
                if schedule.start_offset == 0:
                    result['start_offset_type'] = self.START_OFFSET_ZERO
                elif schedule.start_offset > 0:
                    result['start_offset_type'] = self.START_OFFSET_POSITIVE
                    result['start_offset'] = schedule.start_offset
                else:
                    result['start_offset_type'] = self.START_OFFSET_NEGATIVE
                    result['start_offset'] = abs(schedule.start_offset)

                if schedule.start_day_of_week >= 0:
                    result['start_day_of_week'] = str(schedule.start_day_of_week)

            if schedule.stop_date_case_property_name:
                result['stop_date_case_property_enabled'] = self.YES
                result['stop_date_case_property_name'] = schedule.stop_date_case_property_name

            self.add_initial_for_custom_metadata(result)

        return result

    def get_start_date_layout_fields(self):
        return [
            hqcrispy.B3MultiField(
                _("Start Date"),
                crispy.Div(
                    twbscrispy.InlineField(
                        'start_date_type',
                        data_bind='value: start_date_type',
                    ),
                    css_class='col-sm-8',
                ),
                crispy.Div(
                    twbscrispy.InlineField(
                        'start_date_case_property',
                    ),
                    data_bind="visible: start_date_type() === '%s'" % self.START_DATE_CASE_PROPERTY,
                    css_class='col-sm-4',
                ),
                crispy.Div(
                    twbscrispy.InlineField(
                        'start_date',
                        data_bind='value: start_date',
                    ),
                    data_bind="visible: start_date_type() === '%s'" % self.START_DATE_SPECIFIC_DATE,
                    css_class='col-sm-4',
                ),
                crispy.Div(
                    get_system_admin_label(),
                    data_bind="visible: start_date_type() === '%s'" % self.START_DATE_FROM_VISIT_SCHEDULER,
                ),
                data_bind='visible: usesTimedSchedule',
            ),
            crispy.Div(
                crispy.Field('visit_scheduler_app_and_form_unique_id'),
                hqcrispy.B3MultiField(
                    _("Scheduler: Visit"),
                    crispy.Div(
                        twbscrispy.InlineField('visit_number'),
                        css_class='col-sm-4',
                    ),
                ),
                crispy.Field('visit_window_position'),
                data_bind=(
                    "visible: usesTimedSchedule() && start_date_type() === '%s'" %
                    self.START_DATE_FROM_VISIT_SCHEDULER
                ),
            ),
            hqcrispy.B3MultiField(
                _("Begin"),
                crispy.Div(
                    twbscrispy.InlineField(
                        'start_offset_type',
                        data_bind='value: start_offset_type',
                    ),
                    css_class='col-sm-4',
                ),
                crispy.Div(
                    twbscrispy.InlineField('start_offset'),
                    css_class='col-sm-2',
                    data_bind="visible: start_offset_type() !== '%s'" % self.START_OFFSET_ZERO,
                ),
                crispy.Div(
                    crispy.HTML('<label class="control-label">%s</label>' % _("day(s)")),
                    data_bind="visible: start_offset_type() !== '%s'" % self.START_OFFSET_ZERO,
                ),
                data_bind=("visible: (send_frequency() === '%s' || send_frequency() === '%s') "
                           "&& start_date_type() !== '%s'" %
                           (self.SEND_DAILY, self.SEND_CUSTOM_DAILY, self.START_DATE_SPECIFIC_DATE)),
            ),
            hqcrispy.B3MultiField(
                _("Begin"),
                twbscrispy.InlineField('start_day_of_week'),
                data_bind=("visible: send_frequency() === '%s' && start_date_type() !== '%s'" %
                           (self.SEND_WEEKLY, self.START_DATE_SPECIFIC_DATE)),
            ),
        ]

    def get_recipients_layout_fields(self):
        result = super(ConditionalAlertScheduleForm, self).get_recipients_layout_fields()
        result.extend([
            hqcrispy.B3MultiField(
                _("Custom Recipient"),
                twbscrispy.InlineField('custom_recipient'),
                get_system_admin_label(),
                data_bind="visible: recipientTypeSelected('%s')" %
                          CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM,
            ),
            hqcrispy.B3MultiField(
                _("Username Case Property"),
                twbscrispy.InlineField('username_case_property'),
                data_bind="visible: recipientTypeSelected('%s')" %
                          CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_PROPERTY_USER,
            ),
            hqcrispy.B3MultiField(
                _("Email Case Property"),
                twbscrispy.InlineField('email_case_property'),
                data_bind="visible: recipientTypeSelected('%s')" %
                          CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_PROPERTY_EMAIL,
            ),
        ])
        return result

    def get_advanced_layout_fields(self):
        result = super(ConditionalAlertScheduleForm, self).get_advanced_layout_fields()
        result.extend([
            hqcrispy.B3MultiField(
                _("Restart Schedule"),
                crispy.Div(
                    twbscrispy.InlineField(
                        'reset_case_property_enabled',
                        data_bind='value: reset_case_property_enabled',
                    ),
                    css_class='col-sm-8',
                ),
                crispy.Div(
                    twbscrispy.InlineField(
                        'reset_case_property_name',
                        placeholder=_("case property"),
                    ),
                    data_bind="visible: reset_case_property_enabled() === '%s'" % self.YES,
                    css_class='col-sm-4',
                ),
                crispy.Div(
                    crispy.HTML(
                        '<p class="help-block"><i class="fa fa-info-circle"></i> %s</p>' %
                        _("This cannot be changed after initial configuration."),
                    ),
                    css_class='col-sm-12',
                ),
            ),
            hqcrispy.B3MultiField(
                _("Use case property stop date"),
                crispy.Div(
                    twbscrispy.InlineField(
                        'stop_date_case_property_enabled',
                        data_bind='value: stop_date_case_property_enabled',
                    ),
                    css_class='col-sm-4',
                ),
                crispy.Div(
                    twbscrispy.InlineField(
                        'stop_date_case_property_name',
                        placeholder=_("case property"),
                    ),
                    data_bind="visible: stop_date_case_property_enabled() === '%s'" % self.YES,
                    css_class='col-sm-8',
                ),
            ),
        ])

        if (
            self.is_system_admin
            or self.initial.get('capture_custom_metadata_item') == self.YES
        ):
            result.extend([
                hqcrispy.B3MultiField(
                    _("Capture Custom Data on each SMS"),
                    crispy.Div(
                        twbscrispy.InlineField(
                            'capture_custom_metadata_item',
                            data_bind='value: capture_custom_metadata_item',
                        ),
                        css_class='col-sm-4',
                    ),
                    crispy.Div(
                        get_system_admin_label(),
                        data_bind="visible: capture_custom_metadata_item() === 'Y'",
                    ),
                ),
                crispy.Div(
                    crispy.Field('custom_metadata_item_name'),
                    crispy.Field('custom_metadata_item_value'),
                    data_bind="visible: capture_custom_metadata_item() === 'Y'",
                ),
            ])

        return result

    def clean_start_offset_type(self):
        if (
            self.cleaned_data.get('send_frequency') not in (self.SEND_DAILY, self.SEND_CUSTOM_DAILY)
            or self.cleaned_data.get('start_date_type') == self.START_DATE_SPECIFIC_DATE
        ):
            return None

        value = self.cleaned_data.get('start_offset_type')

        if not value:
            raise ValidationError(_("This field is required"))

        if (
            value == self.START_OFFSET_NEGATIVE
            and self.cleaned_data.get('start_date_type') == self.START_DATE_RULE_TRIGGER
        ):
            raise ValidationError(_("You may not start sending before the day that the rule triggers."))

        return value

    def clean_start_offset(self):
        if (
            self.cleaned_data.get('send_frequency') not in (self.SEND_DAILY, self.SEND_CUSTOM_DAILY)
            or self.cleaned_data.get('start_date_type') == self.START_DATE_SPECIFIC_DATE
            or self.cleaned_data.get('start_offset_type') == self.START_OFFSET_ZERO
        ):
            return None

        return validate_int(self.cleaned_data.get('start_offset'), 1)

    def clean_start_date_type(self):
        if self.cleaned_data_uses_alert_schedule():
            return None

        value = self.cleaned_data.get('start_date_type')
        if not value:
            raise ValidationError(_("This field is required"))

        return value

    def clean_start_date(self):
        if self.cleaned_data.get('start_date_type') != self.START_DATE_SPECIFIC_DATE:
            return None

        return super(ConditionalAlertScheduleForm, self).clean_start_date()

    def clean_start_day_of_week(self):
        if (
            self.cleaned_data.get('send_frequency') != self.SEND_WEEKLY
            or self.cleaned_data.get('start_date_type') == self.START_DATE_SPECIFIC_DATE
        ):
            return None

        value = self.cleaned_data.get('start_day_of_week')
        error = ValidationError(_("Invalid choice selected"))

        try:
            value = int(value)
        except (ValueError, TypeError):
            raise error

        if value < 0 or value > 6:
            raise error

        return value

    def clean_custom_recipient(self):
        recipient_types = self.cleaned_data.get('recipient_types', [])
        custom_recipient = self.cleaned_data.get('custom_recipient')

        if CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM not in recipient_types:
            return None

        if not custom_recipient:
            raise ValidationError(_("This field is required"))

        return custom_recipient

    def clean_reset_case_property_enabled(self):
        value = self.cleaned_data['reset_case_property_enabled']
        if (
            value == self.YES
            and not self.cleaned_data_uses_alert_schedule()
            and self.cleaned_data.get('start_date_type') != self.START_DATE_RULE_TRIGGER
        ):
            raise ValidationError(
                _("This option can only be enabled when the schedule's start date is set automatically.")
            )

        return value

    def clean_reset_case_property_name(self):
        if self.cleaned_data.get('reset_case_property_enabled') == self.NO:
            return None

        value = validate_case_property_name(
            self.cleaned_data.get('reset_case_property_name'),
            allow_parent_case_references=False,
        )

        if value in set([field.name for field in CommCareCase._meta.fields]):
            raise ValidationError(_("Only dynamic case properties are allowed"))

        return value

    def clean_stop_date_case_property_name(self):
        if self.cleaned_data.get('stop_date_case_property_enabled') != self.YES:
            return None

        return validate_case_property_name(
            self.cleaned_data.get('stop_date_case_property_name'),
            allow_parent_case_references=False,
        )

    def clean_start_date_case_property(self):
        if (
            self.cleaned_data_uses_alert_schedule()
            or self.cleaned_data.get('start_date_type') != self.START_DATE_CASE_PROPERTY
        ):
            return None

        return validate_case_property_name(
            self.cleaned_data.get('start_date_case_property'),
            allow_parent_case_references=False,
        )

    def clean_send_time_case_property_name(self):
        if (
            self.cleaned_data_uses_custom_event_definitions()
            or self.cleaned_data_uses_alert_schedule()
            or self.cleaned_data.get('send_time_type') != TimedSchedule.EVENT_CASE_PROPERTY_TIME
        ):
            return None

        return validate_case_property_name(
            self.cleaned_data.get('send_time_case_property_name'),
            allow_parent_case_references=False,
        )

    def clean_visit_scheduler_app_and_form_unique_id(self):
        if self.cleaned_data.get('start_date_type') != self.START_DATE_FROM_VISIT_SCHEDULER:
            return None

        value = self.cleaned_data.get('visit_scheduler_app_and_form_unique_id')
        if not value:
            raise ValidationError(_("This field is required"))

        app_id, form_unique_id = split_combined_id(value)
        form, app = self.get_latest_released_form_and_app(app_id, form_unique_id)

        if isinstance(form, AdvancedForm) and form.schedule and form.schedule.enabled:
            return value

        raise ValidationError(_("The selected form does not have a schedule enabled."))

    def validate_visit(self, form, visit_index):
        try:
            visit = form.schedule.visits[visit_index]
        except IndexError:
            raise ValidationError(
                _("Visit number not found in latest released app build. Please check form configuration.")
            )

        if visit.repeats:
            raise ValidationError(
                _("The referenced visit in the latest released app build is a repeat visit. "
                  "Repeat visits are not supported")
            )

        if not isinstance(visit.expires, int):
            raise ValidationError(
                _("The referenced visit in the latest released app build does not have a window end date. "
                  "Visits which do not have a window end date are not supported")
            )

    def clean_visit_number(self):
        if self.cleaned_data.get('start_date_type') != self.START_DATE_FROM_VISIT_SCHEDULER:
            return None

        visit_scheduler_app_and_form_unique_id = self.cleaned_data.get('visit_scheduler_app_and_form_unique_id')
        if not visit_scheduler_app_and_form_unique_id:
            raise ValidationError(_("Please first select a visit scheduler form"))

        value = self.cleaned_data.get('visit_number')
        if value is None or value <= 0:
            raise ValidationError(_("Please enter a number greater than 0"))

        app_id, form_unique_id = split_combined_id(visit_scheduler_app_and_form_unique_id)
        form, app = self.get_latest_released_form_and_app(app_id, form_unique_id)
        self.validate_visit(form, value - 1)

        return value

    def clean_visit_window_position(self):
        if self.cleaned_data.get('start_date_type') != self.START_DATE_FROM_VISIT_SCHEDULER:
            return None

        value = self.cleaned_data.get('visit_window_position')
        if not value:
            raise ValidationError("This field is required")

        return value

    def clean_custom_metadata_item_name(self):
        if self.cleaned_data.get('capture_custom_metadata_item') != self.YES:
            return None

        value = self.cleaned_data.get('custom_metadata_item_name')
        if not value:
            raise ValidationError(_("This field is required."))

        return value

    def clean_custom_metadata_item_value(self):
        if self.cleaned_data.get('capture_custom_metadata_item') != self.YES:
            return None

        value = self.cleaned_data.get('custom_metadata_item_value')
        if not value:
            raise ValidationError(_("This field is required."))

        return value

    def clean(self):
        recipient_types = self.cleaned_data.get('recipient_types')
        if CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_PROPERTY_EMAIL in recipient_types:
            if self.cleaned_data.get('content') != self.CONTENT_EMAIL:
                raise ValidationError(_("Email case property can only be used with Email content"))

        if self.cleaned_data.get('content') == self.CONTENT_FCM_NOTIFICATION:
            if not settings.FCM_CREDS:
                raise ValidationError(_("Push Notifications is no longer available on this environment."
                                        " Please contact Administrator."))
            if not FCM_NOTIFICATION.enabled(self.domain):
                raise ValidationError(_("Push Notifications is not available for your project."
                                        " Please contact Administrator."))

            recipient_types_choices = dict(self.fields['recipient_types'].choices)
            unsupported_recipient_types = {str(recipient_types_choices[recipient_type])
                                           for recipient_type in recipient_types
                                           if recipient_type not in self.FCM_SUPPORTED_RECIPIENT_TYPES}
            if unsupported_recipient_types:
                raise ValidationError(_("'{}' recipient types are not supported for Push Notifications"
                                        .format(', '.join(unsupported_recipient_types))))

    def distill_start_offset(self):
        send_frequency = self.cleaned_data.get('send_frequency')
        start_offset_type = self.cleaned_data.get('start_offset_type')
        start_date_type = self.cleaned_data.get('start_date_type')

        if (
            send_frequency in (self.SEND_DAILY, self.SEND_CUSTOM_DAILY)
            and start_date_type != self.START_DATE_SPECIFIC_DATE
            and start_offset_type in (self.START_OFFSET_NEGATIVE, self.START_OFFSET_POSITIVE)
        ):
            start_offset = self.cleaned_data.get('start_offset')

            if start_offset is None:
                raise ValidationError(_("This field is required"))

            if start_offset_type == self.START_OFFSET_NEGATIVE:
                return -1 * start_offset
            else:
                return start_offset

        return 0

    def distill_start_day_of_week(self):
        if self.cleaned_data['send_frequency'] != self.SEND_WEEKLY:
            return TimedSchedule.ANY_DAY

        if self.cleaned_data['start_date_type'] == self.START_DATE_SPECIFIC_DATE:
            return self.cleaned_data['start_date'].weekday()

        return self.cleaned_data['start_day_of_week']

    def distill_scheduler_module_info(self):
        if self.cleaned_data.get('start_date_type') != self.START_DATE_FROM_VISIT_SCHEDULER:
            return CreateScheduleInstanceActionDefinition.SchedulerModuleInfo(enabled=False)

        app_id, form_unique_id = split_combined_id(
            self.cleaned_data['visit_scheduler_app_and_form_unique_id']
        )

        return CreateScheduleInstanceActionDefinition.SchedulerModuleInfo(
            enabled=True,
            # The id of the primary application doc
            app_id=app_id,
            form_unique_id=form_unique_id,
            # Convert to 0-based index
            visit_number=self.cleaned_data['visit_number'] - 1,
            window_position=self.cleaned_data['visit_window_position'],
        )

    def distill_recipients(self):
        result = super(ConditionalAlertScheduleForm, self).distill_recipients()
        recipient_types = self.cleaned_data['recipient_types']

        for recipient_type_without_id in (
            CaseScheduleInstanceMixin.RECIPIENT_TYPE_SELF,
            CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_OWNER,
            CaseScheduleInstanceMixin.RECIPIENT_TYPE_LAST_SUBMITTING_USER,
            CaseScheduleInstanceMixin.RECIPIENT_TYPE_PARENT_CASE,
            CaseScheduleInstanceMixin.RECIPIENT_TYPE_ALL_CHILD_CASES,
        ):
            if recipient_type_without_id in recipient_types:
                result.append((recipient_type_without_id, None))

        if CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM in recipient_types:
            custom_recipient_id = self.cleaned_data['custom_recipient']
            result.append((CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM, custom_recipient_id))

        if CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_PROPERTY_USER in recipient_types:
            username_case_property = self.cleaned_data['username_case_property']
            result.append((CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_PROPERTY_USER, username_case_property))
        if CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_PROPERTY_EMAIL in recipient_types:
            email_case_property = self.cleaned_data['email_case_property']
            result.append((CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_PROPERTY_EMAIL, email_case_property))
        return result

    def distill_model_timed_event(self):
        if self.cleaned_data_uses_custom_event_definitions():
            raise ValueError("Cannot use this method with custom event definitions")

        event_type = self.cleaned_data['send_time_type']
        if event_type == TimedSchedule.EVENT_CASE_PROPERTY_TIME:
            return CasePropertyTimedEvent(
                case_property_name=self.cleaned_data['send_time_case_property_name'],
            )

        return super(ConditionalAlertScheduleForm, self).distill_model_timed_event()

    def distill_extra_scheduling_options(self):
        extra_options = super(ConditionalAlertScheduleForm, self).distill_extra_scheduling_options()

        if self.cleaned_data.get('capture_custom_metadata_item') == self.YES:
            extra_options['custom_metadata'] = {
                self.cleaned_data['custom_metadata_item_name']: self.cleaned_data['custom_metadata_item_value']
            }
        else:
            extra_options['custom_metadata'] = {}

        extra_options['stop_date_case_property_name'] = self.cleaned_data['stop_date_case_property_name']

        return extra_options

    def create_rule_action(self, rule, schedule):
        fields = {
            'recipients': self.distill_recipients(),
            'reset_case_property_name': self.cleaned_data['reset_case_property_name'],
            'scheduler_module_info': self.distill_scheduler_module_info().to_json(),
            'start_date_case_property': self.cleaned_data['start_date_case_property'],
            'specific_start_date': self.cleaned_data['start_date'],
        }

        if isinstance(schedule, AlertSchedule):
            fields['alert_schedule'] = schedule
        elif isinstance(schedule, TimedSchedule):
            fields['timed_schedule'] = schedule
        else:
            raise TypeError("Unexpected Schedule type")

        rule.add_action(CreateScheduleInstanceActionDefinition, **fields)

    def edit_rule_action(self, rule, schedule):
        action = rule.caseruleaction_set.all()[0]
        action_definition = action.definition
        self.validate_existing_action_definition(action_definition, schedule)

        action_definition.recipients = self.distill_recipients()
        action_definition.reset_case_property_name = self.cleaned_data['reset_case_property_name']
        action_definition.set_scheduler_module_info(self.distill_scheduler_module_info())
        action_definition.start_date_case_property = self.cleaned_data['start_date_case_property']
        action_definition.specific_start_date = self.cleaned_data['start_date']
        action_definition.save()

    def validate_existing_action_definition(self, action_definition, schedule):
        if not isinstance(action_definition, CreateScheduleInstanceActionDefinition):
            raise TypeError("Expected CreateScheduleInstanceActionDefinition")

        if isinstance(schedule, AlertSchedule):
            if action_definition.alert_schedule_id != schedule.schedule_id:
                raise ValueError("Schedule mismatch")
        elif isinstance(schedule, TimedSchedule):
            if action_definition.timed_schedule_id != schedule.schedule_id:
                raise ValueError("Schedule mismatch")
        else:
            raise TypeError("Unexpected Schedule type")

    def save_rule_action(self, rule, schedule):
        num_actions = rule.caseruleaction_set.count()
        if num_actions == 0:
            self.create_rule_action(rule, schedule)
        elif num_actions == 1:
            self.edit_rule_action(rule, schedule)
        else:
            raise ValueError("Expected 0 or 1 action")

    def save_rule_action_and_schedule(self, rule):
        with transaction.atomic():
            schedule = self.save_schedule()
            self.save_rule_action(rule, schedule)


class ConditionalAlertForm(Form):
    # Prefix to avoid name collisions; this means all input
    # names in the HTML are prefixed with "conditional-alert-"
    prefix = "conditional-alert"

    name = TrimmedCharField(
        label=gettext_lazy("Name"),
        required=True,
        max_length=126,
    )

    def __init__(self, domain, rule, *args, **kwargs):
        self.domain = domain
        self.initial_rule = rule

        if kwargs.get('initial'):
            raise ValueError("Initial values are set by the form")

        if self.initial_rule:
            kwargs['initial'] = self.compute_initial(domain)

        super(ConditionalAlertForm, self).__init__(*args, **kwargs)

        self.helper = HQFormHelper()
        self.helper.form_tag = False

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Basic Information"),
                crispy.Field('name', data_bind="value: name, valueUpdate: 'afterkeydown'"),
            ),
        )

    def compute_initial(self, domain):
        return {
            'name': self.initial_rule.name,
        }

    @property
    def rule_name(self):
        return self.cleaned_data.get('name')


class ConditionalAlertCriteriaForm(CaseRuleCriteriaForm):

    @property
    def show_fieldset_title(self):
        return False

    @property
    def fieldset_help_text(self):
        return _("An instance of the schedule will be created for each "
                 "open case matching all filter criteria below.")

    @property
    def allow_parent_case_references(self):
        return False

    @property
    def allow_case_modified_filter(self):
        return False

    @property
    def allow_case_property_filter(self):
        return True

    @property
    def allow_date_case_property_filter(self):
        return False

    @property
    def allow_regex_case_property_match(self):
        return True

    def set_read_only_fields_during_editing(self):
        # Django also handles keeping the field's value to its initial value no matter what is posted
        # https://docs.djangoproject.com/en/1.11/ref/forms/fields/#disabled

        # Prevent case_type from being changed when we are using the form to edit
        # an existing conditional alert. Being allowed to assume that case_type
        # doesn't change makes it easier to run the rule for this alert.
        self.fields['case_type'].disabled = True

    def set_case_type_choices(self, initial):
        # If this is an edit form, case type won't be editable (see set_read_only_fields_during_editing),
        # so don't bother fetching case types.
        if self.initial_rule:
            self.fields['case_type'].choices = (
                (case_type, case_type) for case_type in [initial or '']
            )
        else:
            super().set_case_type_choices(initial)

    def __init__(self, *args, **kwargs):
        super(ConditionalAlertCriteriaForm, self).__init__(*args, **kwargs)
        if self.initial_rule:
            self.set_read_only_fields_during_editing()
