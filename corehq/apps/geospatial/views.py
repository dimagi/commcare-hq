import json
import jsonschema

from django.urls import reverse
from django.http import HttpResponseRedirect, Http404, HttpResponseBadRequest
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from dimagi.utils.web import json_response

from corehq import toggles
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.geospatial.reports import CaseManagementMap
from corehq.apps.geospatial.forms import GeospatialConfigForm
from .const import POLYGON_COLLECTION_GEOJSON_SCHEMA
from .models import GeoPolygon


def geospatial_default(request, *args, **kwargs):
    return HttpResponseRedirect(CaseManagementMap.get_url(*args, **kwargs))


class GeoPolygonView(BaseDomainView):
    urlname = 'geo_polygon'

    @method_decorator(toggles.GEOSPATIAL.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(GeoPolygonView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        try:
            polygon_id = int(request.GET.get('polygon_id', None))
        except TypeError:
            raise Http404()
        try:
            polygon = GeoPolygon.objects.get(pk=polygon_id)
            assert polygon.domain == self.domain
        except (GeoPolygon.DoesNotExist, AssertionError):
            raise Http404()
        return json_response(polygon.geo_json)

    def post(self, request, *args, **kwargs):
        try:
            geo_json = json.loads(request.body).get('geo_json', None)
        except json.decoder.JSONDecodeError:
            raise HttpResponseBadRequest(
                'POST Body must be a valid json in {"geo_json": <geo_json>} format'
            )

        if not geo_json:
            raise HttpResponseBadRequest('Empty geo_json POST field')

        try:
            jsonschema.validate(geo_json, POLYGON_COLLECTION_GEOJSON_SCHEMA)
        except jsonschema.exceptions.ValidationError:
            raise HttpResponseBadRequest(
                'Invalid GeoJSON, geo_json must be a FeatureCollection of Polygons'
            )
        # Drop ids since they are specific to the Mapbox draw event
        for feature in geo_json["features"]:
            del feature['id']

        geo_polygon = GeoPolygon.objects.create(
            name=geo_json.pop('name'),
            domain=self.domain,
            geo_json=geo_json
        )
        return json_response({
            'id': geo_polygon.id,
        })


class GeospatialConfigPage(BaseDomainView):
    urlname = "geospatial_settings"
    section_name = _("Configuration Settings")
    template_name = "geospatial/settings.html"

    @method_decorator(toggles.GEOSPATIAL.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(GeospatialConfigPage, self).dispatch(request, *args, **kwargs)

    @property
    def section_url(self):
        return reverse(GeospatialConfigPage.urlname, args=(self.domain,))

    @property
    def page_context(self):
        return {
            'form': self.settings_form,
        }

    @property
    def settings_form(self):
        if self.request.method == 'POST':
            return GeospatialConfigForm(self.request.POST)
        return GeospatialConfigForm()

    def post(self, request, *args, **kwargs):
        form = self.settings_form
        # Todo
        return self.get(request, *args, **kwargs)
