from django.http import Http404
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from corehq.apps.domain.views.base import BaseDomainView
from corehq import toggles


class BaseGeospatialView(BaseDomainView):
    urlname = 'maps_page'
    section_name = _("Geospatial")

    def dispatch(self, *args, **kwargs):
        if not toggles.GEOSPATIAL.enabled(self.domain):
            raise Http404
        return super(BaseGeospatialView, self).dispatch(*args, **kwargs)

    @property
    def section_url(self):
        return reverse(BaseGeospatialView.urlname, args=(self.domain,))


class MapView(BaseGeospatialView):
    urlname = 'maps_page'
    template_name = 'map_visualization.html'
    page_title = _("Map Visualization")

    @property
    def page_name(self):
        return _("Map Visualization")

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])
