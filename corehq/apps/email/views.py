from django.shortcuts import render, redirect
from django.utils.translation import gettext as _

from corehq.apps.domain.views import BaseDomainView
from corehq.apps.email.forms import EmailSMTPSettingsForm
from corehq.apps.email.models import EmailSettings


class EmailSMTPSettingsView(BaseDomainView):
    template_name = 'email/email_settings.html'
    urlname = 'email_gateway_settings'
    page_title = _('Email Settings')

    def get(self, request, *args, **kwargs):
        email_settings = EmailSettings.objects.filter(domain=self.domain).first()

        if email_settings:
            form = EmailSMTPSettingsForm(instance=email_settings)
        else:
            form = EmailSMTPSettingsForm()
        return render(request, self.template_name, {'form': form, 'domain': self.domain})

    def post(self, request, *args, **kwargs):
        email_settings, _ = EmailSettings.objects.get_or_create(domain=self.domain)

        form = EmailSMTPSettingsForm(request.POST, instance=email_settings)

        if form.is_valid():
            form.instance.domain = self.domain
            form.save()
            return redirect(EmailSMTPSettingsView.urlname, domain=self.domain)
        else:
            return render(request, self.template_name, {'form': form, 'domain': self.domain})
