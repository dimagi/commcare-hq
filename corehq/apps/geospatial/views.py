import json
import jsonschema

from requests.exceptions import HTTPError

from django.forms.models import model_to_dict
from django.utils.decorators import method_decorator
from django.urls import reverse
from django.http import HttpResponseRedirect, Http404, HttpResponseBadRequest
from django.utils.translation import gettext_lazy as _
from dimagi.utils.web import json_response

from corehq import toggles
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.geospatial.reports import CaseManagementMap
from corehq.apps.geospatial.forms import GeospatialConfigForm
from corehq.util.view_utils import json_error
from .routing_solvers.mapbox_optimize import (
    submit_routing_request,
    routing_status
)

from .const import POLYGON_COLLECTION_GEOJSON_SCHEMA
from .models import GeoPolygon, GeoConfig



def geospatial_default(request, *args, **kwargs):
    return HttpResponseRedirect(CaseManagementMap.get_url(*args, **kwargs))


class MapboxOptimizationV2(BaseDomainView):
    urlname = 'mapbox_routing'

    def get(self, request):
        return geospatial_default(request)

    @json_error
    def post(self, request):
        # Submits the given request JSON to Mapbox Optimize V2 API
        #   and responds with a result ID that can be polled
        request_json = json.loads(request.body.decode('utf-8'))
        try:
            poll_id = submit_routing_request(request_json)
            return json_response(
                {"poll_url": reverse("mapbox_routing_status", args=[self.domain, poll_id])}
            )
        except (jsonschema.exceptions.ValidationError, HTTPError) as e:
            return HttpResponseBadRequest(str(e))

    @method_decorator(toggles.GEOSPATIAL.required_decorator())
    def dispatch(self, request, domain, *args, **kwargs):
        self.domain = domain
        return super(MapboxOptimizationV2, self).dispatch(request, *args, **kwargs)


def mapbox_routing_status(request, domain, poll_id):
    # Todo; handle HTTPErrors
    return routing_status(poll_id)


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
    template_name = "geospatial/settings.html"

    page_name = _("Configuration Settings")
    section_name = _("Geospatial")

    @method_decorator(toggles.GEOSPATIAL.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(GeospatialConfigPage, self).dispatch(request, *args, **kwargs)

    @property
    def section_url(self):
        return reverse(self.urlname, args=(self.domain,))

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain,))

    @property
    def page_context(self):
        return {
            'form': self.settings_form,
            'config': model_to_dict(
                self.config,
                fields=GeospatialConfigForm.Meta.fields
            )
        }

    @property
    def settings_form(self):
        if self.request.method == 'POST':
            return GeospatialConfigForm(self.request.POST, instance=self.config)
        return GeospatialConfigForm(instance=self.config)

    @property
    def config(self):
        try:
            obj = GeoConfig.objects.get(domain=self.domain)
        except GeoConfig.DoesNotExist:
            obj = GeoConfig()
            obj.domain = self.domain
        return obj

    def post(self, request, *args, **kwargs):
        form = self.settings_form

        if not form.is_valid():
            return self.get(request, *args, **kwargs)

        instance = form.save(commit=False)
        instance.domain = self.domain
        instance.save()

        return self.get(request, *args, **kwargs)
