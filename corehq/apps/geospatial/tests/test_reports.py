import doctest
import json
from contextlib import contextmanager
from decimal import Decimal

from nose.tools import assert_equal, assert_raises

from corehq.apps.es import case_search_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.geospatial.reports import (
    CaseGroupingReport,
    geojson_to_es_geoshape,
)
from corehq.apps.geospatial.utils import (
    get_geo_case_property,
    validate_geometry,
)
from corehq.apps.hqcase.case_helper import CaseHelper
from corehq.apps.reports.tests.test_sql_reports import DOMAIN, BaseReportTest
from corehq.util.test_utils import flag_enabled


def test_geojson_to_es_geoshape():
    geojson = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [125.6, 10.1]
        },
        "properties": {
            "name": "Dinagat Islands"
        }
    }
    es_geoshape = geojson_to_es_geoshape(geojson)
    assert_equal(es_geoshape, {
        "type": "point",  # NOTE: lowercase Elasticsearch type
        "coordinates": [125.6, 10.1]
    })


def test_validate_geometry_type():
    geojson_geometry = {
        "type": "Point",
        "coordinates": [125.6, 10.1]
    }
    with assert_raises(ValueError):
        validate_geometry(geojson_geometry)


def test_validate_geometry_schema():
    geojson_geometry = {
        "type": "Polygon",
        "coordinates": [125.6, 10.1]
    }
    with assert_raises(ValueError):
        validate_geometry(geojson_geometry)


@flag_enabled('GEOSPATIAL')
@es_test(requires=[case_search_adapter], setup_class=True)
class TestCaseGroupingReport(BaseReportTest):

    def _get_request(self, **kwargs):
        request = self.factory.get('/some/url', **kwargs)
        request.couch_user = self.couch_user
        request.domain = DOMAIN
        request.can_access_all_locations = True
        return request

    def test_case_row_order(self):
        request = self._get_request()
        report_obj = CaseGroupingReport(request, domain=DOMAIN)
        report_obj.rendered_as = 'view'
        context_data = report_obj.template_context
        expected_columns = ['case_id', 'case_name', 'owner_id', 'owner_name', 'coordinates', 'link']
        self.assertEqual(
            list(context_data['case_row_order'].keys()),
            expected_columns
        )

    def test_bucket_cases(self):
        with self.get_cases() as (porto_novo, bohicon, lagos):
            request = self._get_request()
            report = CaseGroupingReport(
                request,
                domain=DOMAIN,
                in_testing=True,
            )
            json_data = report.json_dict['aaData']

        case_data_by_id = {row[0]: row for row in json_data}
        case_ids = set(case_data_by_id)

        self.assertSetEqual(
            case_ids,
            {porto_novo.case_id, bohicon.case_id, lagos.case_id}
        )

        case_data = case_data_by_id[porto_novo.case_id]
        self.assertListEqual(
            case_data[0:-1],
            [
                porto_novo.case_id,
                'Porto-Novo',
                self.couch_user.user_id,
                self.couch_user.username,
                {'lat': Decimal('6.497222'), 'lng': Decimal('2.605')}
            ]
        )

    def test_bucket_and_polygon_with_hole(self):
        with self.get_cases() as (porto_novo, bohicon, lagos):
            request = self._get_request(data={
                'features': json.dumps(polygon_with_hole)
            })
            report = CaseGroupingReport(
                request,
                domain=DOMAIN,
                in_testing=True,
            )
            json_data = report.json_dict['aaData']
        case_ids = [row[0] for row in json_data]

        self.assertEqual(len(json_data), 1)
        self.assertIn(porto_novo.case_id, case_ids)

    @contextmanager
    def get_cases(self):

        def create_case(name, coordinates):
            helper = CaseHelper(domain=DOMAIN)
            helper.create_case({
                'case_type': 'ville',
                'case_name': name,
                'properties': {
                    geo_property: f'{coordinates} 0 0',
                },
                'owner_id': self.couch_user.get_id,
            })
            return helper.case

        geo_property = get_geo_case_property(DOMAIN)
        porto_novo = create_case('Porto-Novo', '6.497222 2.605')
        bohicon = create_case('Bohicon', '7.2 2.066667')
        lagos = create_case('Lagos', '6.455027 3.384082')
        case_search_adapter.bulk_index([
            porto_novo,
            bohicon,
            lagos
        ], refresh=True)

        try:
            yield porto_novo, bohicon, lagos

        finally:
            case_search_adapter.bulk_delete([
                porto_novo.case_id,
                bohicon.case_id,
                lagos.case_id
            ], refresh=True)
            porto_novo.delete()
            bohicon.delete()
            lagos.delete()


def test_doctests():
    import corehq.apps.geospatial.reports as reports

    results = doctest.testmod(reports)
    assert results.failed == 0


def test_filter_for_two_polygons():
    two_polygons = {
        "2a5ea4f248e76d593d1860fd30ff4d7a": {
            "id": "2a5ea4f248e76d593d1860fd30ff4d7a",
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [
                            3.8611289319507023,
                            10.678207690092108
                        ],
                        [
                            2.224654018272389,
                            10.527070203861257
                        ],
                        [
                            2.2356370713843887,
                            10.062403156135844
                        ],
                        [
                            1.3460097693168223,
                            9.975878699953796
                        ],
                        [
                            1.3789589286527928,
                            9.293710611914307
                        ],
                        [
                            1.6645183095633342,
                            8.957545872249298
                        ],
                        [
                            1.6205860971153925,
                            6.988931314042162
                        ],
                        [
                            1.8072980000180792,
                            6.18155446649547
                        ],
                        [
                            2.729874461421531,
                            6.279818038095172
                        ],
                        [
                            2.8067558332044484,
                            9.011787334706497
                        ],
                        [
                            3.1032982672269895,
                            9.098556718238612
                        ],
                        [
                            3.8611289319507023,
                            10.678207690092108
                        ]
                    ]
                ]
            }
        },
        "f4d8cc04529c256645dd6515f21f5c73": {
            "id": "f4d8cc04529c256645dd6515f21f5c73",
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [
                            2.554145611629849,
                            7.023269537230718
                        ],
                        [
                            2.4333320273990466,
                            7.469976682832254
                        ],
                        [
                            2.2136709651603894,
                            7.622407688138196
                        ],
                        [
                            1.7084505220112192,
                            7.644179142046397
                        ],
                        [
                            1.9940099029217606,
                            6.892443542434833
                        ],
                        [
                            2.554145611629849,
                            7.023269537230718
                        ]
                    ]
                ]
            }
        }
    }
    expected_filter = {
        'bool': {
            'should': (
                {
                    'geo_polygon': {
                        'case_properties.geopoint_value': {
                            'points': [
                                [
                                    3.8611289319507023,
                                    10.678207690092108
                                ],
                                [
                                    2.224654018272389,
                                    10.527070203861257
                                ],
                                [
                                    2.2356370713843887,
                                    10.062403156135844
                                ],
                                [
                                    1.3460097693168223,
                                    9.975878699953796
                                ],
                                [
                                    1.3789589286527928,
                                    9.293710611914307
                                ],
                                [
                                    1.6645183095633342,
                                    8.957545872249298
                                ],
                                [
                                    1.6205860971153925,
                                    6.988931314042162
                                ],
                                [
                                    1.8072980000180792,
                                    6.18155446649547
                                ],
                                [
                                    2.729874461421531,
                                    6.279818038095172
                                ],
                                [
                                    2.8067558332044484,
                                    9.011787334706497
                                ],
                                [
                                    3.1032982672269895,
                                    9.098556718238612
                                ],
                                [
                                    3.8611289319507023,
                                    10.678207690092108
                                ]
                            ]
                        }
                    }
                },
                {
                    'geo_polygon': {
                        'case_properties.geopoint_value': {
                            'points': [
                                [
                                    2.554145611629849,
                                    7.023269537230718
                                ],
                                [
                                    2.4333320273990466,
                                    7.469976682832254
                                ],
                                [
                                    2.2136709651603894,
                                    7.622407688138196
                                ],
                                [
                                    1.7084505220112192,
                                    7.644179142046397
                                ],
                                [
                                    1.9940099029217606,
                                    6.892443542434833
                                ],
                                [
                                    2.554145611629849,
                                    7.023269537230718
                                ]
                            ]
                        }
                    }
                }
            )
        }
    }
    features_json = json.dumps(two_polygons)
    actual_filter = CaseGroupingReport._get_filter_for_features(features_json)
    assert_equal(actual_filter, expected_filter)


def test_one_polygon_with_hole():
    expected_filter = {
        'bool': {
            'should': (
                {
                    'bool': {
                        'filter': (
                            {
                                'geo_polygon': {
                                    'case_properties.geopoint_value': {
                                        'points': [
                                            [
                                                3.8611289319507023,
                                                10.678207690092108
                                            ],
                                            [
                                                2.224654018272389,
                                                10.527070203861257
                                            ],
                                            [
                                                2.2356370713843887,
                                                10.062403156135844
                                            ],
                                            [
                                                1.3460097693168223,
                                                9.975878699953796
                                            ],
                                            [
                                                1.3789589286527928,
                                                9.293710611914307
                                            ],
                                            [
                                                1.6645183095633342,
                                                8.957545872249298
                                            ],
                                            [
                                                1.6205860971153925,
                                                6.988931314042162
                                            ],
                                            [
                                                1.8072980000180792,
                                                6.18155446649547
                                            ],
                                            [
                                                2.729874461421531,
                                                6.279818038095172
                                            ],
                                            [
                                                2.8067558332044484,
                                                9.011787334706497
                                            ],
                                            [
                                                3.1032982672269895,
                                                9.098556718238612
                                            ],
                                            [
                                                3.8611289319507023,
                                                10.678207690092108
                                            ]
                                        ]
                                    }
                                }
                            },
                            {
                                'bool': {
                                    'must_not': {
                                        'geo_polygon': {
                                            'case_properties.geopoint_value': {
                                                'points': [
                                                    [
                                                        2.554145611629849,
                                                        7.023269537230718
                                                    ],
                                                    [
                                                        1.9940099029217606,
                                                        6.892443542434833
                                                    ],
                                                    [
                                                        1.7084505220112192,
                                                        7.644179142046397
                                                    ],
                                                    [
                                                        2.2136709651603894,
                                                        7.622407688138196
                                                    ],
                                                    [
                                                        2.4333320273990466,
                                                        7.469976682832254
                                                    ],
                                                    [
                                                        2.554145611629849,
                                                        7.023269537230718
                                                    ]
                                                ]
                                            }
                                        }
                                    }
                                }
                            }
                        )
                    }
                },  # <-- Note the comma: The value of "should" is a tuple.
            )
        }
    }
    features_json = json.dumps(polygon_with_hole)
    actual_filter = CaseGroupingReport._get_filter_for_features(features_json)
    assert_equal(actual_filter, expected_filter)


polygon_with_hole = {
    "2a5ea4f248e76d593d1860fd30ff4d7a": {
        "id": "2a5ea4f248e76d593d1860fd30ff4d7a",
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    # External ring. Points listed counterclockwise.
                    [
                        3.8611289319507023,
                        10.678207690092108
                    ],
                    [
                        2.224654018272389,
                        10.527070203861257
                    ],
                    [
                        2.2356370713843887,
                        10.062403156135844
                    ],
                    [
                        1.3460097693168223,
                        9.975878699953796
                    ],
                    [
                        1.3789589286527928,
                        9.293710611914307
                    ],
                    [
                        1.6645183095633342,
                        8.957545872249298
                    ],
                    [
                        1.6205860971153925,
                        6.988931314042162
                    ],
                    [
                        1.8072980000180792,
                        6.18155446649547
                    ],
                    [
                        2.729874461421531,
                        6.279818038095172
                    ],
                    [
                        2.8067558332044484,
                        9.011787334706497
                    ],
                    [
                        3.1032982672269895,
                        9.098556718238612
                    ],
                    [
                        3.8611289319507023,
                        10.678207690092108
                    ]
                ],

                # Hole. Points listed clockwise.
                [
                    [
                        2.554145611629849,
                        7.023269537230718
                    ],
                    [
                        1.9940099029217606,
                        6.892443542434833
                    ],
                    [
                        1.7084505220112192,
                        7.644179142046397
                    ],
                    [
                        2.2136709651603894,
                        7.622407688138196
                    ],
                    [
                        2.4333320273990466,
                        7.469976682832254
                    ],
                    [
                        2.554145611629849,
                        7.023269537230718
                    ]
                ]
            ]
        }
    }
}
