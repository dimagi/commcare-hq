from django import forms
from django.template import Context
from django.template.loader import get_template
from django.urls import reverse


class MessageRecipientWidget(forms.Widget):
    def __init__(self, domain, attrs=None, id='message-recipient'):
        super(MessageRecipientWidget, self).__init__(attrs)
        self.domain = domain
        self.id = id
        self.query_url = reverse('possible_sms_recipients', args=[self.domain])

    def render(self, name, value, attrs=None):
        # TODO populate this with inital data if necessary
        return get_template('scheduling/partials/message_recipient_widget.html').render(Context({
            'id': self.id,
            'name': name,
            'value': '',
            'query_url': self.query_url,
            'initial_data': [],
        }))
