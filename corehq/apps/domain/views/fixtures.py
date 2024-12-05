from django.contrib import messages
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from corehq import toggles
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.domain.views.settings import BaseAdminProjectSettingsView
from corehq.apps.locations.forms import LocationFixtureForm
from corehq.apps.locations.models import LocationFixtureConfiguration


class LocationFixtureConfigView(BaseAdminProjectSettingsView):
    urlname = 'location_fixture_config'
    page_title = gettext_lazy('Location Fixture')
    template_name = 'domain/admin/bootstrap3/location_fixture.html'

    @method_decorator(domain_admin_required)
    @method_decorator(toggles.HIERARCHICAL_LOCATION_FIXTURE.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(LocationFixtureConfigView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        location_settings = LocationFixtureConfiguration.for_domain(self.domain)
        form = LocationFixtureForm(request.POST, instance=location_settings)
        if form.is_valid():
            form.save()
            messages.success(request, _("Location configuration updated successfully"))

        return self.get(request, *args, **kwargs)

    @property
    def page_context(self):
        location_settings = LocationFixtureConfiguration.for_domain(self.domain)
        form = LocationFixtureForm(instance=location_settings)
        return {'form': form}
