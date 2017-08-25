from crispy_forms import layout as crispy
from crispy_forms import bootstrap as twbscrispy
from crispy_forms.helper import FormHelper
from django import forms
from django.forms.fields import (
    BooleanField,
    CharField,
    ChoiceField,
    MultipleChoiceField,
)
from django.forms.forms import Form
from django.template import Context
from django.template.loader import get_template
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from corehq.apps.style import crispy as hqcrispy
from corehq.apps.translations.models import StandaloneTranslationDoc
from corehq.apps.users.models import CommCareUser


class MessageRecipientWidget(forms.Widget):
    def __init__(self, domain, readonly, attrs=None, id='message-recipient'):
        super(MessageRecipientWidget, self).__init__(attrs)
        self.domain = domain
        self.id = id
        self.query_url = reverse('possible_sms_recipients', args=[self.domain])
        self.readonly = readonly

    def render(self, name, value, attrs=None):
        initial_value = []
        if value:
            for doc_type, doc_id in value:
                user = CommCareUser.wrap(CommCareUser.get_db().get(doc_id))
                initial_value.append({"id": doc_id, "name": user.raw_username})
        # TODO populate this with inital data if necessary
        return get_template('scheduling/partials/message_recipient_widget.html').render(Context({
            'id': self.id,
            'name': name,
            'value': 'filler' if initial_value else '',
            'query_url': self.query_url,
            'initial_data': initial_value,
            'readonly': self.readonly
        }))


class MessageRecipientField(MultipleChoiceField):
    def to_python(self, value):
        if not value:
            return []
        return value.split(',')

    def validate(self, value):
        # TODO Will need to add more than user ids
        # TODO batch id verification
        for user_id in value:
            CommCareUser.get_db().get(user_id)


class MessageForm(Form):
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
    recipients = MessageRecipientField(
        label=_("Recipient(s)"),
        help_text=_("Type a username, group name or 'send to all'")
    )
    content = ChoiceField(
        required=True,
        label=_("Content"),  # seems like a weird label?
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
            # TODO Recipients isn't set properly
            readonly = (initial.get('send_frequency') == 'immediately')
            message = initial.get('message', dict)
            kwargs['initial']['translate'] = '*' not in kwargs['initial']
            kwargs['initial']['non_translated_message'] = message.get('*', '')
            for lang in self.project_languages:
                kwargs['initial']['message_%s' % lang] = message.get(lang, '')

        super(MessageForm, self).__init__(*args, **kwargs)
        self.fields['recipients'].widget = MessageRecipientWidget(self.domain, readonly)
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
            crispy.Field('recipients'),
            crispy.Field('content'),
            crispy.Field('translate', data_bind='checked: translate'),
            # todo this doesn't hide the label
            crispy.Field('non_translated_message', data_bind='visible: !translate()'),
        ] + [
            crispy.Field('message_%s' % lang, data_bind='visible: translate')
            for lang in self.project_languages
        ]

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
        self.fields['non_translated_message'] = CharField(label=_("Message"), required=False)

        for lang in self.project_languages:
            # TODO support RTL languages
            self.fields['message_%s' % lang] = CharField(
                label="{} ({})".format(_("Message"), lang), required=False
            )

    @property
    def current_values(self):
        values = {}
        for field_name in self.fields.keys():
            values[field_name] = self[field_name].value()
        return values

    def clean_recipients(self):
        data = self.cleaned_data['recipients']

        # Always return a value to use as the new cleaned data, even if
        # this method didn't change it.
        return data
