from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _

from corehq import toggles
from corehq.apps.domain.decorators import domain_admin_required, login_and_domain_required
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.email.forms import EmailSMTPSettingsForm
from corehq.apps.email.models import EmailSettings


@login_and_domain_required
def default(request, domain):
    from corehq.messaging.scheduling.views import MessagingDashboardView
    return HttpResponseRedirect(reverse(MessagingDashboardView.urlname, args=[domain]))


@method_decorator(domain_admin_required, name='dispatch')
@method_decorator(toggles.CUSTOM_EMAIL_GATEWAY.required_decorator(), name='dispatch')
class EmailSMTPSettingsView(BaseDomainView):
    template_name = 'email/email_settings.html'
    urlname = 'email_gateway_settings'
    page_title = _('Email Settings')
    section_name = _('Messaging')

    @property
    def section_url(self):
        return reverse("email_default", args=[self.domain])

    def get(self, request, *args, **kwargs):
        email_settings = EmailSettings.objects.filter(domain=self.domain).first()

        if email_settings:
            form = EmailSMTPSettingsForm(instance=email_settings)
        else:
            form = EmailSMTPSettingsForm()
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
            form.save()
            return redirect(EmailSMTPSettingsView.urlname, domain=self.domain)
        else:
            return render(request, self.template_name, {'form': form, 'domain': self.domain})
