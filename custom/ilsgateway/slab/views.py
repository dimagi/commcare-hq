from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http.response import HttpResponseRedirect, HttpResponseBadRequest
from django.utils.decorators import method_decorator

from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.locations.models import Location, SQLLocation
from corehq.apps.locations.views import LocationsListView
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.style.decorators import use_jquery_ui, use_bootstrap3
from custom.ilsgateway.models import SLABConfig
from custom.ilsgateway.slab.forms import SLABEditLocationForm
from dimagi.utils.couch import CriticalSection
from dimagi.utils.decorators.memoized import memoized


class SLABConfigurationView(LocationsListView):
    template_name = 'ilsgateway/slab/slab_configuration.html'

    @use_bootstrap3
    @use_jquery_ui
    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        return super(SLABConfigurationView, self).dispatch(request, *args, **kwargs)


class SLABEditLocationView(BaseDomainView):
    template_name = 'ilsgateway/slab/edit_location.html'
    page_title = 'Edit location'

    @use_bootstrap3
    @use_jquery_ui
    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        if self.sql_location.location_type.administrative:
            return HttpResponseBadRequest()
        return super(SLABEditLocationView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def location(self):
        return Location.get(self.kwargs['location_id'])

    @property
    @memoized
    def sql_location(self):
        return self.location.sql_location

    def section_url(self):
        return reverse(
            'slab_edit_location',
            kwargs={'domain': self.domain, 'location_id': self.kwargs['location_id']}
        )

    @property
    def page_context(self):
        try:
            slab_config = SLABConfig.objects.get(sql_location=self.sql_location)
            is_pilot = slab_config.is_pilot
            selected_ids = slab_config.closest_supply_points.all().values_list('pk', flat=True)
        except SLABConfig.DoesNotExist:
            is_pilot = False
            selected_ids = []
        form = SLABEditLocationForm(initial={'is_pilot': is_pilot, 'selected_ids': selected_ids})
        form.fields['selected_ids'].choices = self.choices
        return {
            'form': form
        }

    @property
    def choices(self):
        return SLABConfig.objects.filter(is_pilot=True) \
            .exclude(sql_location=self.sql_location).values_list('sql_location__pk', 'sql_location__name')

    def post(self, request, *args, **kwargs):
        form = SLABEditLocationForm(data=request.POST)
        form.fields['selected_ids'].choices = self.choices
        if not form.is_valid():
            return self.get(request, *args, **kwargs)

        cleaned_data = form.clean()
        is_pilot = cleaned_data['is_pilot']
        selected_ids = cleaned_data['selected_ids']
        if is_pilot:
            with CriticalSection(['update-slab-config-for-location-%s' % self.sql_location.location_id]):
                slab_config, _ = SLABConfig.objects.get_or_create(sql_location=self.sql_location)
                slab_config.is_pilot = is_pilot
                slab_config.closest_supply_points.clear()
                slab_config.closest_supply_points.add(
                    *[SQLLocation.objects.get(pk=pk) for pk in selected_ids]
                )
                slab_config.save()
        else:
            SLABConfig.objects.filter(sql_location=self.sql_location).delete()

        messages.success(request, 'Location updated successfully')
        return HttpResponseRedirect(
            reverse('slab_edit_location', kwargs={'domain': self.domain, 'location_id': self.location.get_id}),
        )


class SLABConfigurationReport(CustomProjectReport):

    report_title = 'Pilot Program'
    name = 'Pilot Program'

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        if user and (user.is_superuser or user.is_domain_admin(domain)):
            return True
        else:
            return False

    @classmethod
    def get_url(cls, domain=None, render_as=None, **kwargs):
        return reverse('slab_configuration', args=[domain])
