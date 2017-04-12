from django.contrib import messages
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.motech.forms import OpenmrsInstanceForm
from corehq.toggles import MOTECH
from dimagi.utils.decorators.memoized import memoized

require_motech_permissions = lambda fn: MOTECH.required_decorator()(domain_admin_required(fn))


class MotechSection(BaseDomainView):
    section_name = ugettext_lazy("Motech")

    @property
    def section_url(self):
        return reverse(OpenmrsInstancesMotechView.urlname, args=[self.domain])

    @method_decorator(require_motech_permissions)
    def dispatch(self, *args, **kwargs):
        return super(MotechSection, self).dispatch(*args, **kwargs)


class OpenmrsInstancesMotechView(MotechSection):
    page_title = ugettext_lazy("OpenMRS Servers")
    urlname = 'motech_openmrs_instances'
    template_name = 'motech/motech_openmrs_instances.html'

    @property
    @memoized
    def openmrs_instance_form(self):
        if self.request.method == 'post':
            return OpenmrsInstanceForm(self.request.POST)
        else:
            return OpenmrsInstanceForm()

    @property
    def page_context(self):
        return {
            'openmrs_instance_form': self.openmrs_instance_form,
        }

    def post(self, request, *args, **kwargs):
        if self.openmrs_instance_form.is_valid():
            # self.openmrs_instance_form.save(self.request.couch_user, self.domain)
            messages.success(request, _("Your OpenMRS server settings have been saved!"))
        return self.get(request, *args, **kwargs)
