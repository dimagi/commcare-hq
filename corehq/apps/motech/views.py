from django.contrib import messages
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy, ugettext as _
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.motech.connected_accounts import get_openmrs_account
from corehq.apps.motech.forms import OpenmrsInstanceForm
from corehq.apps.motech.permissions import require_motech_permissions
from dimagi.utils.decorators.memoized import memoized


class MotechSection(BaseDomainView):
    section_name = ugettext_lazy("Motech")

    @property
    def section_url(self):
        return reverse(OpenmrsInstancesMotechView.urlname, args=[self.domain])

    @method_decorator(require_motech_permissions)
    def dispatch(self, *args, **kwargs):
        return super(MotechSection, self).dispatch(*args, **kwargs)


class OpenmrsInstancesMotechView(MotechSection):
    page_title = ugettext_lazy("OpenMRS Server")
    urlname = 'motech_openmrs_instances'
    template_name = 'motech/motech_openmrs_instances.html'

    @property
    @memoized
    def openmrs_instance_form(self):
        account = get_openmrs_account(self.domain)
        if account:
            initial = {'username': account.server_username, 'server_url': account.server_url}
        else:
            initial = {}
        if self.request.method == 'POST':
            return OpenmrsInstanceForm(self.request.POST, initial=initial)
        else:
            return OpenmrsInstanceForm(initial=initial)

    @property
    def page_context(self):
        return {
            'openmrs_instance_form': self.openmrs_instance_form,
        }

    def post(self, request, *args, **kwargs):
        if self.openmrs_instance_form.is_valid():
            self.openmrs_instance_form.save(self.domain)
            messages.success(request, _("Your OpenMRS server settings have been saved!"))
        return self.get(request, *args, **kwargs)


class OpenmrsConceptMotechView(MotechSection):
    page_title = ugettext_lazy("OpenMRS Concepts")
    urlname = 'motech_openmrs_concepts'
    template_name = 'motech/motech_openmrs_concepts.html'
