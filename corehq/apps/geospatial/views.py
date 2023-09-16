import json
import jsonschema
from requests.exceptions import HTTPError

from django.conf import settings
from django.core.paginator import Paginator
from django.http import (
    HttpResponseRedirect,
    Http404,
    HttpResponseBadRequest,
    JsonResponse,
)
from django.forms.models import model_to_dict
from django.utils.decorators import method_decorator
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET
from dimagi.utils.web import json_response
from dimagi.utils.couch.bulk import get_docs

from corehq import toggles
from corehq.apps.es import CaseSearchES, UserES
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.data_dictionary.models import CaseProperty
from corehq.apps.domain.views.base import BaseDomainView
from corehq.form_processor.models import CommCareCase
from corehq.apps.users.models import CommCareUser
from corehq.apps.geospatial.reports import CaseManagementMap
from corehq.apps.geospatial.forms import GeospatialConfigForm
from corehq.util.view_utils import json_error
from .routing_solvers.mapbox_optimize import (
    submit_routing_request,
    routing_status
)

from .const import POLYGON_COLLECTION_GEOJSON_SCHEMA
from .models import GeoPolygon, GeoConfig
from .utils import (
    get_geo_case_property,
    get_geo_user_property,
    set_case_gps_property,
    set_user_gps_property,
    get_lat_lon_from_dict,
)


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
        gps_case_props = CaseProperty.objects.filter(
            case_type__domain=self.domain,
            data_type=CaseProperty.DataType.GPS,
        )
        return {
            'form': self.settings_form,
            'config': model_to_dict(
                self.config,
                fields=GeospatialConfigForm.Meta.fields
            ),
            'gps_case_props_deprecated_state': {
                prop.name: prop.deprecated for prop in gps_case_props
            }
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


class GPSCaptureView(BaseDomainView):
    urlname = 'gps_capture'
    template_name = 'gps_capture.html'

    page_name = _("Manage GPS Data")
    section_name = _("Geospatial")

    @method_decorator(toggles.GEOSPATIAL.required_decorator())
    def dispatch(self, *args, **kwargs):
        return super(GPSCaptureView, self).dispatch(*args, **kwargs)

    @property
    def section_url(self):
        return reverse(self.urlname, args=(self.domain,))

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain,))

    @property
    def page_context(self):
        data_type = self.request.GET.get('data_type', 'case')
        return {
            'data_type': data_type,
            'mapbox_access_token': settings.MAPBOX_ACCESS_TOKEN,
        }

    @method_decorator(toggles.GEOSPATIAL.required_decorator())
    def post(self, request, *args, **kwargs):
        json_data = json.loads(request.body)
        data_type = json_data.get('data_type', None)
        data_item = json_data.get('data_item', None)

        if data_type == 'case':
            set_case_gps_property(request.domain, data_item)
        elif data_type == 'user':
            set_user_gps_property(request.domain, data_item)

        return json_response({
            'status': 'success'
        })


@require_GET
@login_and_domain_required
def get_paginated_cases_or_users_without_gps(request, domain):
    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 5))
    query = request.GET.get('query', '')
    case_or_user = request.GET.get('data_type', 'case')

    if case_or_user == 'user':
        data = _get_paginated_users_without_gps(domain, page, limit, query)
    else:
        data = _get_paginated_cases_without_gps(domain, page, limit, query)
    return JsonResponse(data)


def _get_paginated_cases_without_gps(domain, page, limit, query):
    location_prop_name = get_geo_case_property(domain)
    case_ids = (
        CaseSearchES()
        .domain(domain)
        .is_closed(False)
        .case_property_missing(location_prop_name)
        .search_string_query(query, ['name'])
        .sort('server_modified_on', desc=True)
    ).get_ids()

    paginator = Paginator(case_ids, limit)
    case_ids_page = list(paginator.get_page(page))
    cases = CommCareCase.objects.get_cases(case_ids_page, domain, ordered=True)
    case_data = []
    for case_obj in cases:
        lat, lon = get_lat_lon_from_dict(case_obj.case_json, location_prop_name)
        case_data.append(
            {
                'id': case_obj.case_id,
                'name': case_obj.name,
                'lat': lat,
                'lon': lon,
            }
        )
    return {
        'items': case_data,
        'total': paginator.count,
    }


def _get_paginated_users_without_gps(domain, page, limit, query):
    location_prop_name = get_geo_user_property(domain)
    query = (
        UserES()
        .domain(domain)
        .mobile_users()
        .missing_or_empty_metadata_property(location_prop_name)
        .search_string_query(query, ['username'])
        .sort('created_on', desc=True)
    )

    paginator = Paginator(query.get_ids(), limit)
    user_ids_page = list(paginator.get_page(page))
    user_docs = get_docs(CommCareUser.get_db(), keys=user_ids_page)
    user_data = []
    for user_doc in user_docs:
        lat, lon = get_lat_lon_from_dict(user_doc['user_data'], location_prop_name)
        user_data.append(
            {
                'id': user_doc['_id'],
                'name': user_doc['username'].split('@')[0],
                'lat': lat,
                'lon': lon,
            }
        )
    return {
        'items': user_data,
        'total': paginator.count,
    }


@require_GET
@login_and_domain_required
def get_users_with_gps(request, domain):
    location_prop_name = get_geo_user_property(domain)
    users = CommCareUser.by_domain(domain)
    user_data = [
        {
            'id': user.user_id,
            'username': user.raw_username,
            'gps_point': user.pop_metadata(key=location_prop_name),
        } for user in users
    ]

    return json_response({'user_data': user_data})
