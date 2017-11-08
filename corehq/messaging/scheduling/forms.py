from __future__ import absolute_import
from crispy_forms import layout as crispy
from crispy_forms import bootstrap as twbscrispy
from crispy_forms.helper import FormHelper
from django.forms.fields import (
    BooleanField,
    CharField,
    ChoiceField,
)
from django.forms.forms import Form
from django.forms.widgets import Textarea
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.translations.models import StandaloneTranslationDoc
from corehq.apps.users.models import CommCareUser


class RecipientField(CharField):
    def to_python(self, value):
        if not value:
            return []
        return value.split(',')


class ScheduleForm(Form):
    schedule_name = CharField(
        required=True,
        label=_('Schedule Name'),
        max_length=1000,
    )
    send_frequency = ChoiceField(
        required=True,
        label=_('Send'),
        choices=(
            ('immediately', _('Immediately')),
        )
    )
    recipients = RecipientField(
        label=_("Recipient(s)"),
        help_text=_("Type a username, group name or location"),
    )
    content = ChoiceField(
        required=True,
        label=_("What to send"),
        choices=(
            ('sms', _('SMS')),
            # ('email', _('Email')),
            # ('sms_survey', _('SMS Survey')),
            # ('ivr_survey', _('IVR Survey')),
        )
    )
    translate = BooleanField(
        label=_("Translate this message"),
        required=False
    )

    def __init__(self, *args, **kwargs):
        self.domain = kwargs.pop('domain')
        initial = kwargs.get('initial')
        readonly = False
        if initial:
            readonly = (initial.get('send_frequency') == 'immediately')
            message = initial.get('message', {})
            kwargs['initial']['translate'] = '*' not in message
            kwargs['initial']['non_translated_message'] = message.get('*', '')
            for lang in self.project_languages:
                kwargs['initial']['message_%s' % lang] = message.get(lang, '')

        super(ScheduleForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-2 col-md-2 col-lg-2'
        self.helper.field_class = 'col-sm-10 col-md-3 col-lg-3'
        self.add_content_fields()

        if readonly:
            for field_name, field in self.fields.items():
                field.disabled = True

        layout_fields = [
            crispy.Field('schedule_name'),
            crispy.Field('send_frequency'),
            crispy.Field(
                'recipients',
                data_bind='value: message_recipients.value',
                placeholder=_("Select some recipients")
            ),
            crispy.Field('content'),
            crispy.Field('translate', data_bind='checked: translate'),
            crispy.Div(
                crispy.Field('non_translated_message'),
                data_bind='visible: !translate()',
            ),
        ]
        translated_fields = [crispy.Field('message_%s' % lang) for lang in self.project_languages]
        layout_fields.append(
            crispy.Div(*translated_fields, data_bind='visible: translate()')
        )

        if not readonly:
            layout_fields += [
                hqcrispy.FormActions(
                    twbscrispy.StrictButton(
                        _("Save"),
                        css_class='btn-primary',
                        type='submit',
                    ),
                ),
            ]
        self.helper.layout = crispy.Layout(*layout_fields)

    @cached_property
    def project_languages(self):
        doc = StandaloneTranslationDoc.get_obj(self.domain, 'sms')
        return getattr(doc, 'langs', ['en'])

    def add_content_fields(self):
        self.fields['non_translated_message'] = CharField(label=_("Message"), required=False, widget=Textarea)

        for lang in self.project_languages:
            # TODO support RTL languages
            self.fields['message_%s' % lang] = CharField(
                label="{} ({})".format(_("Message"), lang), required=False, widget=Textarea
            )

    @property
    def current_values(self):
        values = {}
        for field_name in self.fields.keys():
            values[field_name] = self[field_name].value()
        return values

    def clean_recipients(self):
        data = self.cleaned_data['recipients']
        # TODO Will need to add more than user ids
        # TODO batch id verification
        for user_id in data:
            user = CommCareUser.get_db().get(user_id)
            assert user['domain'] == self.domain, "User must be in the same domain"

        return data
