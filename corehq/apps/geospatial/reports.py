import json

from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop

from jsonobject.exceptions import BadValueError

from couchforms.geopoint import GeoPoint

from corehq.apps.case_search.const import CASE_PROPERTIES_PATH
from corehq.apps.es import CaseSearchES, filters
from corehq.apps.es.case_search import (
    PROPERTY_GEOPOINT_VALUE,
    PROPERTY_KEY,
    wrap_case_search_hit,
    case_property_missing,
)
from corehq.apps.reports.standard import ProjectReport
from corehq.apps.reports.standard.cases.basic import CaseListMixin
from corehq.apps.reports.standard.cases.case_list_explorer import XpathCaseSearchFilterMixin
from corehq.apps.reports.standard.cases.data_sources import CaseDisplayES
from corehq.util.quickcache import quickcache

from .dispatchers import CaseManagementMapDispatcher
from .es import (
    BUCKET_CASES_AGG,
    CASE_PROPERTIES_AGG,
    CASE_PROPERTY_AGG,
    GEOHASHES_AGG,
    apply_geohash_agg,
    find_precision,
)
from .models import GeoPolygon
from .utils import (
    geojson_to_es_geoshape,
    get_geo_case_property,
    validate_geometry,
)


class BaseCaseMapReport(ProjectReport, CaseListMixin, XpathCaseSearchFilterMixin):
    fields = [
        'corehq.apps.reports.standard.cases.filters.XPathCaseSearchFilter',
        'corehq.apps.reports.filters.case_list.CaseListFilter',
        'corehq.apps.reports.filters.select.CaseTypeFilter',
        'corehq.apps.reports.filters.select.SelectOpenCloseFilter',
    ]

    section_name = gettext_noop("Data")

    dispatcher = CaseManagementMapDispatcher

    search_class = CaseSearchES

    @property
    def template_context(self):
        # Whatever is specified here can be accessed through initial_page_data
        context = super(BaseCaseMapReport, self).template_context
        context.update({
            'mapbox_access_token': settings.MAPBOX_ACCESS_TOKEN,
            'saved_polygons': [
                {'id': p.id, 'name': p.name, 'geo_json': p.geo_json}
                for p in GeoPolygon.objects.filter(domain=self.domain).all()
            ],
        })
        return context

    def _build_query(self):
        query = super()._build_query()
        geo_case_property = get_geo_case_property(self.domain)
        query = query.NOT(case_property_missing(geo_case_property))
        query = self.apply_xpath_case_search_filter(query)
        return query

    def _get_geo_location(self, case):
        geo_case_property = get_geo_case_property(self.domain)
        geo_point = case.get_case_property(geo_case_property)
        try:
            geo_point = GeoPoint.from_string(geo_point, flexible=True)
            return {"lat": geo_point.latitude, "lng": geo_point.longitude}
        except BadValueError:
            return None

    @property
    def rows(self):
        raise NotImplementedError()


class CaseManagementMap(BaseCaseMapReport):
    name = gettext_noop("Case Management Map")
    slug = "case_management_map"

    base_template = "geospatial/map_visualization_base.html"
    report_template_path = "map_visualization.html"

    def default_report_url(self):
        return reverse('geospatial_default', args=[self.request.project.name])

    @property
    def headers(self):
        from corehq.apps.reports.datatables import (
            DataTablesColumn,
            DataTablesHeader,
        )
        headers = DataTablesHeader(
            DataTablesColumn(_("case_id"), prop_name="type.exact"),
            DataTablesColumn(_("gps_point"), prop_name="type.exact"),
            DataTablesColumn(_("link"), prop_name="name.exact", css_class="case-name-link"),
        )
        headers.custom_sort = [[2, 'desc']]
        return headers

    @property
    def rows(self):
        cases = []
        for row in self.es_results['hits'].get('hits', []):
            display = CaseDisplayES(
                self.get_case(row), self.timezone, self.individual
            )
            case = wrap_case_search_hit(row)
            coordinates = self._get_geo_location(case)
            cases.append([
                display.case_id,
                coordinates,
                display.case_link
            ])
        return cases


class CaseGroupingReport(BaseCaseMapReport):
    name = gettext_noop('Case Grouping')
    slug = 'case_grouping_map'

    base_template = 'geospatial/case_grouping_map_base.html'
    report_template_path = 'case_grouping_map.html'

    default_rows = 1
    force_page_size = True
    sortable = False

    @property
    def headers(self):
        from corehq.apps.reports.datatables import (
            DataTablesColumn,
            DataTablesHeader,
        )
        return DataTablesHeader(
            DataTablesColumn(_("Case ID"), prop_name='case_id'),
            DataTablesColumn(_("Case Name"), prop_name='case_name'),
            DataTablesColumn(_("Owner ID"), prop_name='owner_id'),
            DataTablesColumn(_("Owner Name"), prop_name='owner_name'),
            DataTablesColumn(_("Case Coordinates"), prop_name='coordinates'),
            DataTablesColumn(_("Link"), prop_name='link'),
        )

    @property
    def template_context(self):
        context = super().template_context
        context['case_row_order'] = {column.prop_name: index for index, column in enumerate(self.headers)}
        return context

    def _base_query(self):
        # Override function to skip default pagination
        return self.search_class().domain(self.domain)

    @property
    def rows(self):
        """
            Returns cases for the current bucket/page

            Each page is a bucket of filtered cases grouped together.
            We first load all buckets of filtered cases,
            and then find the current bucket via index/page number to get the geohash
            And then we filter cases simply for the geohash corresponding to the bucket
        """
        buckets = self._get_buckets()
        if not buckets:
            return []

        # self.pagination.start is the page number
        # (self.pagination.count is always treated as 1)
        bucket = buckets[self.pagination.start]
        # Example bucket:
        #     {
        #         'key': 't0'
        #         'doc_count': 1,
        #         'bucket_cases': {
        #             'bounds': {
        #                 'bottom_right': {
        #                     'lat': 4.912349972873926,
        #                     'lon': 52.374080987647176,
        #                 },
        #                 'top_left': {
        #                     'lat': 4.912349972873926,
        #                     'lon': 52.374080987647176,
        #                 },
        #             },
        #         },
        #     }
        bounds = bucket[BUCKET_CASES_AGG]['bounds']

        # If there is only one case in the bucket, then the bounds will
        # be the geo_point of that case, and top_left and bottom_right
        # will be the same.
        #
        # If they are the same, then the geo_bounding_box filter will
        # error in Elasticsearch 5.6. (This is not a problem in
        # Elasticsearch 8+, where we can use the bucket key, which is
        # its geohash, to select the cases in the bucket.)
        #
        # So we shift the top left and bottom right by 0.000_01 degrees,
        # or roughly 1 metre.
        if bounds['top_left']['lat'] == bounds['bottom_right']['lat']:
            bounds['top_left']['lat'] += 0.000_01
            bounds['bottom_right']['lat'] -= 0.000_01
        if bounds['top_left']['lon'] == bounds['bottom_right']['lon']:
            bounds['top_left']['lon'] -= 0.000_01
            bounds['bottom_right']['lon'] += 0.000_01

        query = super()._build_query()  # `super()` so as not to filter
        filters_ = [filters.geo_bounding_box(
            field=PROPERTY_GEOPOINT_VALUE,
            top_left=bounds['top_left'],
            bottom_right=bounds['bottom_right'],
        )]
        if self.request.GET.get('features'):
            features_filter = self._get_filter_for_features(
                self.request.GET['features']
            )
            filters_.append(features_filter)
        query = self._filter_query(query, filters_)
        es_results = query.run().raw

        cases = []
        for row in es_results['hits'].get('hits', []):
            display = CaseDisplayES(
                self.get_case(row), self.timezone, self.individual
            )
            case = wrap_case_search_hit(row)
            coordinates = self._get_geo_location(case)
            case_owner_type, case_owner = display.owner
            cases.append([
                display.case_id,
                display.case_name,
                display.owner_id,
                case_owner['name'],
                coordinates,
                display.case_link
            ])
        return cases

    @quickcache(['self.domain', 'self.shared_pagination_GET_params'], timeout=15 * 60)
    def _get_buckets(self):
        query = self._build_query()
        query = self._aggregate_query(query)
        es_results = query.run().raw
        if es_results is None:
            return []
        return (
            es_results['aggregations']
            [CASE_PROPERTIES_AGG]
            [CASE_PROPERTY_AGG]
            [GEOHASHES_AGG]
            ['buckets']
        )

    def _aggregate_query(self, query):
        """
        Returns ``query`` with geohash grid aggregation applied.
        """
        case_property = get_geo_case_property(self.domain)
        if 'precision' in self.request.GET:
            precision = self.request.GET['precision']
        else:
            precision = find_precision(query, case_property)
        return apply_geohash_agg(query, case_property, precision)

    @property
    def total_records(self):
        """
        Returns the number of buckets.

        We are showing buckets of cases so,
        total number of records = number of buckets.
        """
        buckets = self._get_buckets()
        return len(buckets)

    def _build_query(self):
        """
        Returns a filtered, unaggregated, unpaginated ESQuery.
        """
        query = super()._build_query()
        if self.request.GET.get('features'):
            features_filter = self._get_filter_for_features(
                self.request.GET['features']
            )
            query = self._filter_query(query, [features_filter])
        return query

    @staticmethod
    def _get_filter_for_features(features_json):
        """
        Returns an Elasticsearch filter to select for cases within the
        polygons defined by GeoJSON ``features_json``.

        Raises ValueError on invalid ``features_json``.

        Example value of features::

            {
              "1fe8e9a47059aa0d24d3bb518dd32cec": {
                "id": "1fe8e9a47059aa0d24d3bb518dd32cec",
                "type": "Feature",
                "properties": {},
                "geometry": {
                  "type": "Polygon",
                  "coordinates": [
                    [  /* exterior ring */
                      [
                        1.7739302693154002,
                        6.30270638391498
                      ],
                      /* At least three more points, given
                         counterclockwise. The last point will equal the
                         first. */
                    ],
                    /* interior rings / holes. Points are given
                       clockwise. */
                  ]
                }
              },
              "e732a9da883ad59534ff7b6284eeff4a": {
                "id": "e732a9da883ad59534ff7b6284eeff4a",
                "type": "Feature",
                "properties": {},
                "geometry": {
                  "type": "Polygon",
                  "coordinates": [
                    [
                      [
                        0.7089909368813494,
                        7.1851152290118705
                      ],
                      /* ... */
                    ]
                  ]
                }
              }
            }

        """
        try:
            features = json.loads(features_json)
        except json.JSONDecodeError:
            raise ValueError(f'{features_json!r} parameter is not valid JSON')
        polygon_filters = []
        for feature in features.values():
            validate_geometry(feature['geometry'])
            polygon = geojson_to_es_geoshape(feature)
            # The first list of coordinates is the exterior ring, and
            # the rest are interior rings, i.e. holes.
            # https://datatracker.ietf.org/doc/html/rfc7946#section-3.1.6
            exterior_coordinates = polygon['coordinates'][0]
            exterior_filter = filters.geo_polygon(
                field=PROPERTY_GEOPOINT_VALUE,
                points=exterior_coordinates,
            )
            if len(polygon['coordinates']) > 1:
                # Use AND NOT to exclude holes from the polygon. (Using
                # the geo_shape filter in Elasticsearch 8+, this should
                # be unnecessary.)
                interior_filters = []
                for interior_coordinates in polygon['coordinates'][1:]:
                    hole = filters.geo_polygon(
                        field=PROPERTY_GEOPOINT_VALUE,
                        points=interior_coordinates,
                    )
                    interior_filters.append(filters.NOT(hole))
                polygon_filters.append(filters.AND(
                    exterior_filter,
                    *interior_filters
                ))
            else:
                polygon_filters.append(exterior_filter)
        return filters.OR(*polygon_filters)

    def _filter_query(self, query, filters_):
        """
        Prepends the geo case property name filter to a list of
        ``filters_``, and filters ``query`` by ``filters_``.
        """
        if filters_:
            case_property = get_geo_case_property(self.domain)
            filters_.insert(0, filters.term(
                field=PROPERTY_KEY,
                value=case_property
            ))
            query = query.nested(CASE_PROPERTIES_PATH, *filters_)
        return query
