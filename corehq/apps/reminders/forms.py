from __future__ import absolute_import
from __future__ import unicode_literals
import copy
import json
import re
from crispy_forms.bootstrap import InlineField
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from crispy_forms import bootstrap as twbscrispy
from corehq.apps.hqwebapp import crispy as hqcrispy
from django.urls import reverse
from django.template.loader import render_to_string
from datetime import time
from django.conf import settings
from django.core.exceptions import ValidationError
from django.forms.fields import *
from django.forms.forms import Form
from django import forms
from django.forms import Field, Widget
from corehq.apps.reminders.util import DotExpandedDict, get_form_list
from corehq.apps.groups.models import Group
from corehq.apps.sms.models import Keyword
from corehq.util.python_compatibility import soft_assert_type_text
from dimagi.utils.couch.database import iter_docs
from memoized import memoized

from .models import (
    RECIPIENT_CASE,
    RECIPIENT_SURVEY_SAMPLE,
    RECIPIENT_OWNER,
    METHOD_SMS,
    METHOD_SMS_SURVEY,
    RECIPIENT_USER_GROUP,
)
from dateutil.parser import parse
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
from corehq.apps.app_manager.models import Form as CCHQForm
from dimagi.utils.django.fields import TrimmedCharField
import six

NO_RESPONSE = "none"

KEYWORD_CONTENT_CHOICES = (
    (METHOD_SMS, ugettext_lazy("SMS")),
    (METHOD_SMS_SURVEY, ugettext_lazy("SMS Survey")),
    (NO_RESPONSE, ugettext_lazy("No Response")),
)

KEYWORD_RECIPIENT_CHOICES = (
    (RECIPIENT_USER_GROUP, ugettext_lazy("Mobile Worker Group")),
    (RECIPIENT_OWNER, ugettext_lazy("The case's owner")),
)


def form_choices(domain):
    available_forms = get_form_list(domain)
    return [(form['code'], form['name']) for form in available_forms]


def validate_time(value):
    if isinstance(value, time):
        return value
    error_msg = _("Please enter a valid time from 00:00 to 23:59.")
    time_regex = re.compile(r"^\d{1,2}:\d\d(:\d\d){0,1}$")
    if not isinstance(value, six.string_types) or time_regex.match(value) is None:
        raise ValidationError(error_msg)
    if isinstance(value, six.string_types):
        soft_assert_type_text(value)
    try:
        return parse(value).time()
    except Exception:
        raise ValidationError(error_msg)


def validate_form_unique_id(form_unique_id, domain):
    error_msg = _('Invalid form chosen.')
    try:
        form = CCHQForm.get_form(form_unique_id)
        app = form.get_app()
    except Exception:
        raise ValidationError(error_msg)

    if app.domain != domain:
        raise ValidationError(error_msg)

    return form_unique_id


class RecordListWidget(Widget):
    
    # When initialized, expects to be passed attrs={"input_name" : < first dot-separated name of all related records in the html form >}
    
    def value_from_datadict(self, data, files, name, *args, **kwargs):
        input_name = self.attrs["input_name"]
        raw = {}
        for key in data:
            if key.startswith(input_name + "."):
                raw[key] = data[key]
        
        data_dict = DotExpandedDict(raw)
        data_list = []
        if len(data_dict) > 0:
            for key in sorted(six.iterkeys(data_dict[input_name])):
                data_list.append(data_dict[input_name][key])
        
        return data_list

    def render(self, name, value, attrs=None):
        return render_to_string('reminders/partials/record_list_widget.html', {
            'value': value,
            'name': name,
        })


class RecordListField(Field):
    required = None
    label = None
    initial = None
    widget = None
    help_text = None
    
    # When initialized, expects to be passed kwarg input_name, which is the first dot-separated name of all related records in the html form

    def __init__(self, *args, **kwargs):
        input_name = kwargs.pop('input_name')
        kwargs['widget'] = RecordListWidget(attrs={"input_name" : input_name})
        super(RecordListField, self).__init__(*args, **kwargs)

    def clean(self, value):
        return value


class KeywordForm(Form):
    _cchq_domain = None
    _sk_id = None
    keyword = CharField(label=ugettext_noop("Keyword"))
    description = TrimmedCharField(label=ugettext_noop("Description"))
    override_open_sessions = BooleanField(
        required=False,
        initial=False,
        label=ugettext_noop("Override open SMS Surveys"),
    )
    allow_keyword_use_by = ChoiceField(
        required=False,
        label=ugettext_noop("Allow Keyword Use By"),
        initial='any',
        choices=(
            ('any', ugettext_noop("Both Mobile Workers and Cases")),
            ('users', ugettext_noop("Mobile Workers Only")),
            ('cases', ugettext_noop("Cases Only")),
        )
    )
    sender_content_type = ChoiceField(
        label=ugettext_noop("Send to Sender"),
    )
    sender_message = TrimmedCharField(
        required=False,
        label=ugettext_noop("Message"),
    )
    sender_form_unique_id = ChoiceField(
        required=False,
        label=ugettext_noop("Survey"),
    )
    other_recipient_content_type = ChoiceField(
        required=False,
        label=ugettext_noop("Notify Another Person"),
        initial=NO_RESPONSE,
    )
    other_recipient_type = ChoiceField(
        required=False,
        initial=False,
        label=ugettext_noop("Recipient"),
        choices=KEYWORD_RECIPIENT_CHOICES,
    )
    other_recipient_id = ChoiceField(
        required=False,
        label=ugettext_noop("Group Name"),
    )
    other_recipient_message = TrimmedCharField(
        required=False,
        label=ugettext_noop("Message"),
    )
    other_recipient_form_unique_id = ChoiceField(
        required=False,
        label=ugettext_noop("Survey"),
    )
    process_structured_sms = BooleanField(
        required=False,
        label=ugettext_noop("Process incoming keywords as a Structured Message"),
    )
    structured_sms_form_unique_id = ChoiceField(
        required=False,
        label=ugettext_noop("Survey"),
    )
    use_custom_delimiter = BooleanField(
        required=False,
        label=ugettext_noop("Use Custom Delimiter"),
    )
    delimiter = TrimmedCharField(
        required=False,
        label=ugettext_noop("Please Specify Delimiter"),
    )
    use_named_args_separator = BooleanField(
        required=False,
        label=ugettext_noop("Use Joining Character"),
    )
    use_named_args = BooleanField(
        required=False,
        label=ugettext_noop("Use Named Answers"),
    )
    named_args_separator = TrimmedCharField(
        required=False,
        label=ugettext_noop("Please Specify Joining Characcter"),
    )
    named_args = RecordListField(
        input_name="named_args",
        initial=[],
    )

    def __init__(self, *args, **kwargs):
        if 'domain' in kwargs:
            self._cchq_domain = kwargs.pop('domain')

        self.process_structured_sms = False
        if 'process_structured' in kwargs:
            self.process_structured_sms = kwargs.pop('process_structured')

        super(KeywordForm, self).__init__(*args, **kwargs)

        self.fields['sender_content_type'].choices = self.content_type_choices
        self.fields['other_recipient_content_type'].choices = self.content_type_choices

        self.fields['other_recipient_id'].choices = self.group_choices
        self.fields['sender_form_unique_id'].choices = self.form_choices
        self.fields['other_recipient_form_unique_id'].choices = self.form_choices
        self.fields['structured_sms_form_unique_id'].choices = self.form_choices

        from corehq.apps.reminders.views import KeywordsListView
        self.helper = FormHelper()
        self.helper.form_class = "form form-horizontal"
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'

        layout_fields = [
            crispy.Fieldset(
                _('Basic Information'),
                crispy.Field(
                    'keyword',
                    data_bind="value: keyword, "
                              "valueUpdate: 'afterkeydown', "
                              "event: {keyup: updateExampleStructuredSMS}",
                ),
                crispy.Field(
                    'description',
                    data_bind="text: description",
                ),
            ),
        ]
        if self.process_structured_sms:
            layout_fields.append(
                crispy.Fieldset(
                    _("Structured Message Options"),
                    crispy.Field(
                        'structured_sms_form_unique_id',
                        data_bind="value: structuredSmsFormUniqueId",
                    ),
                    hqcrispy.B3MultiField(
                        _("Delimiters"),
                        crispy.Div(
                            crispy.Div(
                                InlineField(
                                    twbscrispy.PrependedText('use_custom_delimiter', '',
                                                             data_bind="checked: useCustomDelimiter, "
                                                                       "click: updateExampleStructuredSMS"),

                                    block_css_class="span2",
                                ),
                                css_class='col-md-4 col-lg-4'
                            ),
                            crispy.Div(
                                InlineField(
                                    'delimiter',
                                    data_bind="value: delimiter, "
                                              "valueUpdate: 'afterkeydown', "
                                              "event: {keyup: updateExampleStructuredSMS},"
                                              "visible: useCustomDelimiter",
                                    block_css_class="span4",
                                ),
                                css_class='col-md-4 col-lg-4'
                            )

                        ),
                    ),
                    hqcrispy.B3MultiField(
                        _("Named Answers"),
                        crispy.Div(
                            InlineField(
                                twbscrispy.PrependedText('use_named_args', '',
                                                         data_bind="checked: useNamedArgs, "
                                                                   "click: updateExampleStructuredSMS"),

                            ),
                            css_class='col-md-4 col-lg-4'
                        ),

                        hqcrispy.ErrorsOnlyField('named_args'),
                        crispy.Div(
                            data_bind="template: {"
                                      " name: 'ko-template-named-args', "
                                      " data: $data"
                                      "}, "
                                      "visible: useNamedArgs",
                        ),
                    ),
                    hqcrispy.B3MultiField(
                        _("Joining Characters"),
                        crispy.Div(
                            crispy.Div(
                                InlineField(
                                    twbscrispy.PrependedText(
                                        'use_named_args_separator', '',
                                        data_bind="checked: useNamedArgsSeparator, "
                                                  "click: updateExampleStructuredSMS"
                                    ),
                                ),
                                css_class='col-md-4 col-lg-4'
                            ),

                            crispy.Div(
                                InlineField(
                                    'named_args_separator',
                                    data_bind="value: namedArgsSeparator, "
                                              "valueUpdate: 'afterkeydown', "
                                              "event: {keyup: updateExampleStructuredSMS},"
                                              "visible: useJoiningCharacter",
                                ),
                                css_class='col-md-6 col-lg-4'
                            )

                        ),
                        data_bind="visible: useNamedArgs",
                    ),
                    hqcrispy.B3MultiField(
                        _("Example Structured Message"),
                        crispy.HTML('<pre style="background: white;" '
                                    'data-bind="text: exampleStructuredSms">'
                                    '</pre>'),
                    ),
                ),
            )
        layout_fields.extend([
            crispy.Fieldset(
                _("Response"),
                crispy.Field(
                    'sender_content_type',
                    data_bind="value: senderContentType",
                ),
                crispy.Div(
                    crispy.Field(
                        'sender_message',
                        data_bind="text: senderMessage",
                    ),
                    data_bind="visible: isMessageSMS",
                ),
                crispy.Div(
                    crispy.Field(
                        'sender_form_unique_id',
                        data_bind="value: senderFormUniqueId"
                    ),
                    data_bind="visible: isMessageSurvey",
                ),
                crispy.Field(
                    'other_recipient_content_type',
                    data_bind="value: otherRecipientContentType",
                ),
                hqcrispy.B3MultiField(
                    "",
                    crispy.Div(
                        crispy.HTML(
                            '<h4 style="margin-bottom: 20px;">%s</h4>'
                            % _("Recipient Information"),
                        ),
                        crispy.Field(
                            'other_recipient_type',
                            data_bind="value: otherRecipientType",
                        ),
                        crispy.Div(
                            crispy.Field(
                                'other_recipient_id',
                                data_bind="value: otherRecipientId",
                            ),
                            data_bind="visible: showRecipientGroup",
                        ),
                        crispy.Div(
                            crispy.Field(
                                'other_recipient_message',
                                data_bind="value: otherRecipientMessage",
                            ),
                            data_bind="visible: otherRecipientContentType() == 'sms'",
                        ),
                        crispy.Div(
                            crispy.Field(
                                'other_recipient_form_unique_id',
                                data_bind="value: otherRecipientFormUniqueId",
                            ),
                            data_bind="visible: otherRecipientContentType() == 'survey'",
                        ),
                        css_class="well",
                        data_bind="visible: notifyOthers",
                    ),
                ),
            ),
            crispy.Fieldset(
                _("Advanced Options"),
                twbscrispy.PrependedText(
                    'override_open_sessions', '',
                    data_bind="checked: overrideOpenSessions",
                ),
                'allow_keyword_use_by',
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Save"),
                    css_class='btn-primary',
                    type='submit',
                ),
                crispy.HTML('<a href="%s" class="btn btn-default">Cancel</a>'
                            % reverse(KeywordsListView.urlname, args=[self._cchq_domain]))
            ),
        ])
        self.helper.layout = crispy.Layout(*layout_fields)

    @property
    def content_type_choices(self):
        return KEYWORD_CONTENT_CHOICES

    @property
    @memoized
    def group_choices(self):
        group_ids = Group.ids_by_domain(self._cchq_domain)
        groups = []
        for group_doc in iter_docs(Group.get_db(), group_ids):
            groups.append((group_doc['_id'], group_doc['name']))
        return groups

    @property
    @memoized
    def form_choices(self):
        return form_choices(self._cchq_domain)

    @property
    def current_values(self):
        values = {}
        for field_name in self.fields.keys():
            values[field_name] = self[field_name].value()
        return values

    def clean_keyword(self):
        value = self.cleaned_data.get("keyword")
        if value is not None:
            value = value.strip().upper()
        if value is None or value == "":
            raise ValidationError(_("This field is required."))
        if len(value.split()) > 1:
            raise ValidationError(_("Keyword should be one word."))
        duplicate = Keyword.get_keyword(self._cchq_domain, value)
        if duplicate and duplicate.couch_id != self._sk_id:
            raise ValidationError(_("Keyword already exists."))
        return value

    def clean_sender_message(self):
        value = self.cleaned_data.get("sender_message")
        if self.cleaned_data.get("sender_content_type") == METHOD_SMS:
            if value is None or value == "":
                raise ValidationError(_("This field is required."))
            return value
        else:
            return None

    def clean_sender_form_unique_id(self):
        value = self.cleaned_data.get("sender_form_unique_id")
        if self.cleaned_data.get("sender_content_type") == METHOD_SMS_SURVEY:
            if value is None:
                raise ValidationError(_(
                    "Please create a form first, and then add a keyword "
                    "for it."
                ))
            validate_form_unique_id(value, self._cchq_domain)
            return value
        else:
            return None

    def clean_other_recipient_message(self):
        value = self.cleaned_data.get("other_recipient_message")
        if self.cleaned_data.get("other_recipient_content_type") == METHOD_SMS:
            if value is None or value == "":
                raise ValidationError(_("This field is required."))
            return value
        else:
            return None

    def clean_other_recipient_form_unique_id(self):
        value = self.cleaned_data.get("other_recipient_form_unique_id")
        if self.cleaned_data.get("other_recipient_content_type") == METHOD_SMS_SURVEY:
            if value is None:
                raise ValidationError(_(
                    "Please create a form first, and then "
                    "add a keyword for it."
                ))
            validate_form_unique_id(value, self._cchq_domain)
            return value
        else:
            return None

    def clean_structured_sms_form_unique_id(self):
        value = self.cleaned_data.get("structured_sms_form_unique_id")
        if self.process_structured_sms:
            if value is None:
                raise ValidationError(_(
                    "Please create a form first, and then add a "
                    "keyword for it."
                ))
            validate_form_unique_id(value, self._cchq_domain)
            return value
        else:
            return None

    def clean_delimiter(self):
        value = self.cleaned_data.get("delimiter", None)
        if self.process_structured_sms and self.cleaned_data["use_custom_delimiter"]:
            if value is None or value == "":
                raise ValidationError(_("This field is required."))
            return value
        else:
            return None

    def clean_named_args(self):
        if self.process_structured_sms and self.cleaned_data["use_named_args"]:
            use_named_args_separator = self.cleaned_data["use_named_args_separator"]
            value = self.cleaned_data.get("named_args")
            data_dict = {}
            for d in value:
                name = d["name"].strip().upper()
                xpath = d["xpath"].strip()
                if name == "" or xpath == "":
                    raise ValidationError(_(
                        "Name and xpath are both required fields."
                    ))
                for k, v in data_dict.items():
                    if (not use_named_args_separator
                        and (k.startswith(name) or name.startswith(k))
                    ):
                        raise ValidationError(
                            _("Cannot have two names overlap: ") + "(%s, %s)"
                            % (k, name)
                        )
                    if use_named_args_separator and k == name:
                        raise ValidationError(
                            _("Cannot use the same name twice: ") + name
                        )
                    if v == xpath:
                        raise ValidationError(
                            _("Cannot reference the same xpath twice: ") + xpath
                        )
                data_dict[name] = xpath
            return data_dict
        else:
            return {}

    def clean_named_args_separator(self):
        value = self.cleaned_data["named_args_separator"]
        if (self.process_structured_sms
            and self.cleaned_data["use_named_args"]
            and self.cleaned_data["use_named_args_separator"]
        ):
            if value is None or value == "":
                raise ValidationError(_("This field is required."))
            if value == self.cleaned_data["delimiter"]:
                raise ValidationError(_(
                    "Delimiter and joining character cannot be the same."
                ))
            return value
        else:
            return None

    def clean_other_recipient_type(self):
        if self.cleaned_data['other_recipient_content_type'] == NO_RESPONSE:
            return None
        value = self.cleaned_data["other_recipient_type"]
        if value == RECIPIENT_OWNER:
            if self.cleaned_data['allow_keyword_use_by'] != 'cases':
                raise ValidationError(_(
                    "In order to send to the case's owner you must restrict "
                    "keyword initiation only to cases."
                ))
        return value

    def clean_other_recipient_id(self):
        if self.cleaned_data['other_recipient_content_type'] == NO_RESPONSE:
            return None
        value = self.cleaned_data["other_recipient_id"]
        recipient_type = self.cleaned_data.get("other_recipient_type", None)
        if recipient_type == RECIPIENT_USER_GROUP:
            try:
                g = Group.get(value)
                assert g.doc_type == "Group"
                assert g.domain == self._cchq_domain
            except Exception:
                raise ValidationError("Invalid Group.")
            return value
        else:
            return None
