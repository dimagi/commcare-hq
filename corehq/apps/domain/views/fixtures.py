from __future__ import absolute_import, unicode_literals

from django.utils.decorators import method_decorator
from django.contrib import messages
from django.utils.translation import ugettext as _, ugettext_lazy

from corehq import toggles
from corehq.apps.calendar_fixture.forms import CalendarFixtureForm
from corehq.apps.calendar_fixture.models import CalendarFixtureSettings
from corehq.apps.locations.forms import LocationFixtureForm
from corehq.apps.locations.models import LocationFixtureConfiguration
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.domain.views.settings import BaseAdminProjectSettingsView


class CalendarFixtureConfigView(BaseAdminProjectSettingsView):
    urlname = 'calendar_fixture_config'
    page_title = ugettext_lazy('Calendar Fixture')
    template_name = 'domain/admin/calendar_fixture.html'

    @method_decorator(domain_admin_required)
    @method_decorator(toggles.CUSTOM_CALENDAR_FIXTURE.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(CalendarFixtureConfigView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        calendar_settings = CalendarFixtureSettings.for_domain(self.domain)
        form = CalendarFixtureForm(request.POST, instance=calendar_settings)
        if form.is_valid():
            form.save()
            messages.success(request, _("Calendar configuration updated successfully"))

        return self.get(request, *args, **kwargs)

    @property
    def page_context(self):
        calendar_settings = CalendarFixtureSettings.for_domain(self.domain)
        form = CalendarFixtureForm(instance=calendar_settings)
        return {'form': form}


class LocationFixtureConfigView(BaseAdminProjectSettingsView):
    urlname = 'location_fixture_config'
    page_title = ugettext_lazy('Location Fixture')
    template_name = 'domain/admin/location_fixture.html'

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
