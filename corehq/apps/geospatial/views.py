import json

from django.conf import settings
from django.core.paginator import Paginator
from django.http import (
    Http404,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET

import jsonschema
from memoized import memoized

from dimagi.utils.couch.database import iter_docs
from dimagi.utils.web import json_request, json_response

from corehq import toggles
from corehq.apps.data_dictionary.models import CaseProperty
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.es import CaseSearchES, UserES
from corehq.apps.es.users import missing_or_empty_user_data_property
from corehq.apps.geospatial.filters import GPSDataFilter
from corehq.apps.geospatial.forms import GeospatialConfigForm
from corehq.apps.geospatial.reports import CaseManagementMap
from corehq.apps.hqwebapp.crispy import CSS_ACTION_CLASS
from corehq.apps.hqwebapp.decorators import use_datatables, use_jquery_ui
from corehq.apps.reports.generic import get_filter_classes
from corehq.apps.reports.standard.cases.basic import CaseListMixin
from corehq.apps.reports.standard.cases.filters import CaseSearchFilter
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.form_processor.models import CommCareCase
from corehq.util.timezones.utils import get_timezone

from .const import GPS_POINT_CASE_PROPERTY, POLYGON_COLLECTION_GEOJSON_SCHEMA
from .models import GeoConfig, GeoPolygon
from .utils import (
    create_case_with_gps_property,
    get_geo_case_property,
    get_geo_user_property,
    get_lat_lon_from_dict,
    set_case_gps_property,
    set_user_gps_property,
)


def geospatial_default(request, *args, **kwargs):
    return HttpResponseRedirect(CaseManagementMap.get_url(*args, **kwargs))


class CaseDisbursementAlgorithm(BaseDomainView):
    urlname = "case_disbursement"

    def post(self, request, domain, *args, **kwargs):
        config = GeoConfig.objects.get(domain=domain)
        request_json = json.loads(request.body.decode('utf-8'))

        solver_class = config.disbursement_solver
        result = solver_class(request_json).solve(config=config)

        return json_response({
            'assignments': result['assigned'],
            'unassigned': result['unassigned'],
            'parameters': result['parameters'],
        })


@method_decorator(toggles.GEOSPATIAL.required_decorator(), name="dispatch")
class GeoPolygonListView(BaseDomainView):
    urlname = 'geo_polygons'

    def post(self, request, *args, **kwargs):
        try:
            geo_json = json.loads(request.body).get('geo_json', None)
        except json.decoder.JSONDecodeError:
            return HttpResponseBadRequest(
                'POST Body must be a valid json in {"geo_json": <geo_json>} format'
            )

        if not geo_json:
            return HttpResponseBadRequest('Empty geo_json POST field')

        try:
            jsonschema.validate(geo_json, POLYGON_COLLECTION_GEOJSON_SCHEMA)
        except jsonschema.exceptions.ValidationError:
            return HttpResponseBadRequest(
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


@method_decorator(toggles.GEOSPATIAL.required_decorator(), name="dispatch")
class GeoPolygonDetailView(BaseDomainView):
    urlname = 'geo_polygon'

    def get(self, request, *args, **kwargs):
        try:
            polygon = GeoPolygon.objects.get(pk=kwargs["pk"], domain=self.domain)
        except (ValueError, GeoPolygon.DoesNotExist):
            raise Http404()
        return JsonResponse(polygon.geo_json)

    def delete(self, request, *args, **kwargs):
        try:
            polygon = GeoPolygon.objects.get(pk=kwargs["pk"], domain=self.domain)
            polygon.delete()
        except (ValueError, GeoPolygon.DoesNotExist):
            raise Http404()

        return JsonResponse({
            'success': True,
            'message': _("Saved area '{polygon_name}' has been successfully deleted.").format(
                polygon_name=polygon.name,
            )
        })


class BaseConfigView(BaseDomainView):
    section_name = _("Data")

    @method_decorator(toggles.GEOSPATIAL.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(BaseConfigView, self).dispatch(request, *args, **kwargs)

    @property
    def section_url(self):
        return reverse(self.urlname, args=(self.domain,))

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain,))

    @property
    def config(self):
        try:
            obj = GeoConfig.objects.get(domain=self.domain)
        except GeoConfig.DoesNotExist:
            obj = GeoConfig()
            obj.domain = self.domain
        return obj

    @property
    def config_form(self):
        if self.request.method == 'POST':
            return self.form_class(self.request.POST, instance=self.config)
        return self.form_class(instance=self.config)

    @property
    def page_context(self):
        return {
            'form': self.config_form,
        }

    def post(self, request, *args, **kwargs):
        form = self.config_form

        if not form.is_valid():
            return self.get(request, *args, **kwargs)

        instance = form.save(commit=False)
        instance.domain = self.domain
        instance.save()

        return self.get(request, *args, **kwargs)


class GeospatialConfigPage(BaseConfigView):
    urlname = "geospatial_settings"
    template_name = "geospatial/settings.html"

    page_name = _("Configuration Settings")

    form_class = GeospatialConfigForm

    @property
    def page_context(self):
        context = super().page_context

        gps_case_props = CaseProperty.objects.filter(
            case_type__domain=self.domain,
            data_type=CaseProperty.DataType.GPS,
        )
        gps_case_props_deprecated_state = {prop.name: prop.deprecated for prop in gps_case_props}
        if GPS_POINT_CASE_PROPERTY not in gps_case_props_deprecated_state:
            gps_case_props_deprecated_state[GPS_POINT_CASE_PROPERTY] = False
        context.update({
            'config': self.config.as_dict(fields=GeospatialConfigForm.Meta.fields),
            'gps_case_props_deprecated_state': gps_case_props_deprecated_state,
            'target_grouping_name': GeoConfig.TARGET_SIZE_GROUPING,
            'min_max_grouping_name': GeoConfig.MIN_MAX_GROUPING,
            'road_network_algorithm_slug': GeoConfig.ROAD_NETWORK_ALGORITHM,
        })
        return context


class GPSCaptureView(BaseDomainView):
    urlname = 'gps_capture'
    template_name = 'gps_capture_view.html'

    page_name = _("Manage GPS Data")
    section_name = _("Data")

    fields = [
        'corehq.apps.reports.filters.case_list.CaseListFilter',
        'corehq.apps.reports.filters.select.CaseTypeFilter',
        'corehq.apps.reports.filters.select.SelectOpenCloseFilter',
        'corehq.apps.reports.standard.cases.filters.CaseSearchFilter',
        'corehq.apps.geospatial.filters.GPSDataFilter',
    ]

    @use_datatables
    @use_jquery_ui
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
        case_types = CaseProperty.objects.filter(
            case_type__domain=self.domain,
            data_type=CaseProperty.DataType.GPS,
        ).values_list('case_type__name', flat=True).distinct()

        page_context = {
            'mapbox_access_token': settings.MAPBOX_ACCESS_TOKEN,
            'case_types_with_gps': list(case_types),
            'couch_user_username': self.request.couch_user.raw_username,
        }
        page_context.update(self._case_filters_context())
        return page_context

    def _case_filters_context(self):
        # set up context for report filters template to be used for case filtering
        return {
            'report': {
                'title': self.page_name,
                'section_name': self.section_name,
                'show_filters': True,
            },
            'report_filters': [
                dict(field=f.render(), slug=f.slug) for f in self.filter_classes
            ],
            'report_filter_form_action_css_class': CSS_ACTION_CLASS,
        }

    @property
    @memoized
    def filter_classes(self):
        timezone = get_timezone(self.request, self.domain)
        return get_filter_classes(self.fields, self.request, self.domain, timezone)

    @method_decorator(toggles.GEOSPATIAL.required_decorator())
    def post(self, request, *args, **kwargs):
        json_data = json.loads(request.body)
        data_type = json_data.get('data_type', None)
        data_item = json_data.get('data_item', None)
        create_case = json_data.get('create_case', False)

        if data_type == 'case':
            if create_case:
                data_item['owner_id'] = data_item['owner_id'] or request.couch_user.user_id
                create_case_with_gps_property(request.domain, data_item)
            else:
                set_case_gps_property(request.domain, data_item)
        elif data_type == 'user':
            set_user_gps_property(request.domain, data_item)

        return json_response({
            'status': 'success'
        })


@require_GET
@login_and_domain_required
def get_paginated_cases_or_users(request, domain):
    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 5))
    query = request.GET.get('query', '')
    case_or_user = request.GET.get('data_type', 'case')

    if case_or_user == 'user':
        data = _get_paginated_users_without_gps(domain, page, limit, query)
    else:
        data = GetPaginatedCases(request, domain).get_paginated_cases_without_gps(domain, page, limit)
    return JsonResponse(data)


class GetPaginatedCases(CaseListMixin):
    search_class = CaseSearchES

    def __init__(self, request, domain, **kwargs):
        # override super class corehq.apps.reports.generic.GenericReportView init method to
        # avoid failures for missing expected properties for a report and keep only necessary properties
        self.request = request
        self.request_params = json_request(self.request.GET)
        self.domain = domain

    def _base_query(self):
        # override CaseListMixin _base_query method to avoid pagination in ES and handle it later
        return (
            self.search_class()
            .domain(self.domain)
        )

    def get_paginated_cases_without_gps(self, domain, page, limit):
        show_cases_with_missing_gps_data_only = True

        if GPSDataFilter(self.request, self.domain).show_all:
            show_cases_with_missing_gps_data_only = False

        cases_query = self._build_query()
        location_prop_name = get_geo_case_property(domain)
        if show_cases_with_missing_gps_data_only:
            cases_query = cases_query.case_property_missing(location_prop_name)

        search_string = CaseSearchFilter.get_value(self.request, self.domain)
        if search_string:
            cases_query = cases_query.set_query({"query_string": {"query": search_string}})

        cases_query = cases_query.sort('server_modified_on', desc=True)
        case_ids = cases_query.get_ids()

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
    res = (
        UserES()
        .domain(domain)
        .mobile_users()
        .missing_or_empty_user_data_property(location_prop_name)
        .search_string_query(query, ['username'])
        .fields(['_id', 'username'])
        .sort('created_on', desc=True)
        .start((page - 1) * limit)
        .size(limit)
        .run()
    )
    return {
        'items': [
            {
                'id': hit['_id'],
                'name': hit['username'].split('@')[0],
                'lat': '',
                'lon': '',
            } for hit in res.hits
        ],
        'total': res.total,
    }


@require_GET
@login_and_domain_required
def get_users_with_gps(request, domain):
    location_prop_name = get_geo_user_property(domain)
    query = (
        UserES()
        .domain(domain)
        .mobile_users()
        .NOT(missing_or_empty_user_data_property(location_prop_name))
    )
    selected_location_id = request.GET.get('location_id')
    if selected_location_id:
        query = query.location(selected_location_id)
    user_ids = query.scroll_ids()
    users = map(CouchUser.wrap_correctly, iter_docs(CommCareUser.get_db(), user_ids))
    user_data = [
        {
            'id': user.user_id,
            'username': user.raw_username,
            'gps_point': user.get_user_data(domain).get(location_prop_name, ''),
        } for user in users
    ]

    return json_response({'user_data': user_data})
