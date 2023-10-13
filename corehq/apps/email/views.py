from secrets import token_urlsafe

from django import forms
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy

from corehq import toggles
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.email.forms import EmailSMTPSettingsForm
from corehq.apps.email.models import EmailSettings
from corehq.messaging.scheduling.views import MessagingDashboardView


@method_decorator(domain_admin_required, name='dispatch')
@method_decorator(toggles.CUSTOM_EMAIL_GATEWAY.required_decorator(), name='dispatch')
class EmailSMTPSettingsView(BaseDomainView):
    template_name = 'email/email_settings.html'
    urlname = 'email_gateway_settings'
    page_title = gettext_lazy('Email Settings')
    section_name = gettext_lazy('Messaging')

    @property
    def section_url(self):
        return reverse(MessagingDashboardView.urlname, args=[self.domain])

    def get(self, request, *args, **kwargs):
        email_settings = EmailSettings.objects.filter(domain=self.domain).first()

        if email_settings:
            form = EmailSMTPSettingsForm(instance=email_settings)
            if email_settings.use_tracking_headers is False:
                form.fields['sns_secret'].widget = forms.HiddenInput()
        else:
            form = EmailSMTPSettingsForm()
            form.fields['sns_secret'].widget = forms.HiddenInput()

        return render(request, self.template_name, {
            'form': form,
            'domain': self.domain,
            'current_page': {'title': self.page_title},
            'section': {'page_name': self.section_name, 'url': self.section_url}
        })

    def post(self, request, *args, **kwargs):
        email_settings, _ = EmailSettings.objects.get_or_create(domain=self.domain)

        form = EmailSMTPSettingsForm(request.POST, instance=email_settings)

        if form.is_valid():
            form.instance.domain = self.domain
            if form.instance.use_tracking_headers and not form.instance.sns_secret:
                form.instance.sns_secret = token_urlsafe(16)

            form.save()
            return redirect(EmailSMTPSettingsView.urlname, domain=self.domain)
        else:
            return render(request, self.template_name, {'form': form, 'domain': self.domain})
