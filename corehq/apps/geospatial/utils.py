from dataclasses import asdict, dataclass, field

import jsonschema
from jsonobject.exceptions import BadValueError

from casexml.apps.case.mock import CaseBlock
from couchforms.geopoint import GeoPoint
from dimagi.utils.couch.cache.cache_core import get_redis_client

from corehq.apps.geospatial.models import GeoConfig
from corehq.apps.hqcase.case_helper import CaseHelper
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import CommCareUser
from corehq.const import ONE_DAY
from corehq.util.quickcache import quickcache


@quickcache(['domain'], timeout=24 * 60 * 60)
def get_geo_case_property(domain):
    try:
        config = GeoConfig.objects.get(domain=domain)
    except GeoConfig.DoesNotExist:
        config = GeoConfig()
    return config.case_location_property_name


@quickcache(['domain'], timeout=24 * 60 * 60)
def get_geo_user_property(domain):
    try:
        config = GeoConfig.objects.get(domain=domain)
    except GeoConfig.DoesNotExist:
        config = GeoConfig()
    return config.user_location_property_name


def _format_coordinates(lat, lon):
    return f"{lat} {lon} 0.0 0.0"


def create_case_with_gps_property(domain, case_data):
    location_prop_name = get_geo_case_property(domain)
    data = {
        'properties': {
            location_prop_name: _format_coordinates(case_data['lat'], case_data['lon'])
        },
        'case_name': case_data['name'],
        'case_type': case_data['case_type'],
        'owner_id': case_data['owner_id'],
    }
    helper = CaseHelper(domain=domain)
    helper.create_case(data, user_id=case_data['owner_id'])


def set_case_gps_property(domain, case_data, create_case=False):
    location_prop_name = get_geo_case_property(domain)
    data = {
        'properties': {
            location_prop_name: _format_coordinates(case_data['lat'], case_data['lon'])
        }
    }
    helper = CaseHelper(domain=domain, case_id=case_data['id'])
    helper.update(data)


def set_user_gps_property(domain, user_data):
    location_prop_name = get_geo_user_property(domain)
    user = CommCareUser.get_by_user_id(user_data['id'])
    user.get_user_data(domain)[location_prop_name] = _format_coordinates(user_data['lat'], user_data['lon'])
    user.save()


def get_lat_lon_from_dict(data, key):
    try:
        gps_location_prop = data[key]
        geo_point = GeoPoint.from_string(gps_location_prop, flexible=True)
        lat, lon = (str(geo_point.latitude), str(geo_point.longitude))
    except (KeyError, BadValueError):
        lat, lon = ('', '')
    return lat, lon


def validate_geometry(geojson_geometry):
    """
    Validates the GeoJSON geometry, and checks that its type is
    supported.
    """
    # Case properties that are set as the "GPS" data type in the Data
    # Dictionary are given the ``geo_point`` data type in Elasticsearch.
    #
    # In Elasticsearch 8+, the flexible ``geo_shape`` query supports the
    # ``geo_point`` type, but Elasticsearch 5.6 does not. Instead, we
    # have to filter GPS case properties using the ``geo_polygon``
    # query, which is **deprecated in Elasticsearch 7.12**.
    #
    # TODO: After Elasticsearch is upgraded, switch from
    #       filters.geo_polygon to filters.geo_shape, and update this
    #       list of supported types. See filters.geo_shape for more
    #       details. (Norman, 2023-11-01)
    supported_types = (
        'Polygon',  # Supported by Elasticsearch 5.6

        # Available for the `geo_point` data type using the `geo_shape`
        # filter from Elasticsearch 8+:
        #
        # 'Point',
        # 'LineString',
        # 'MultiPoint',
        # 'MultiLineString',
        # 'MultiPolygon',

        # 'GeometryCollection', YAGNI
    )
    if geojson_geometry['type'] not in supported_types:
        raise ValueError(
            f"{geojson_geometry['type']} is not a supported geometry type"
        )

    # The complete schema is at https://geojson.org/schema/GeoJSON.json
    schema = {
        "type": "object",
        "required": ["type", "coordinates"],
        "properties": {
            "type": {
                "type": "string"
            },
            "coordinates": {
                "type": "array",
                # Polygon-specific properties:
                "items": {
                    "type": "array",
                    "minItems": 4,
                    "items": {
                        "type": "array",
                        "minItems": 2,
                        "items": {
                            "type": "number"
                        }
                    }
                }
            },
            # Unused but valid
            "bbox": {
                "type": "array",
                "minItems": 4,
                "items": {
                    "type": "number"
                }
            }
        }
    }
    try:
        jsonschema.validate(geojson_geometry, schema)
    except jsonschema.ValidationError as err:
        raise ValueError(
            f'{geojson_geometry!r} is not a valid GeoJSON geometry'
        ) from err


def geojson_to_es_geoshape(geojson):
    """
    Given a GeoJSON dict, returns a GeoJSON Geometry dict, with "type"
    given as an Elasticsearch type (i.e. in lowercase).

    More info:

    * `The GeoJSON specification (RFC 7946) <https://datatracker.ietf.org/doc/html/rfc7946>`_
    * `Elasticsearch types <https://www.elastic.co/guide/en/elasticsearch/reference/5.6/geo-shape.html#input-structure>`_

    """  # noqa: E501
    es_geoshape = geojson['geometry'].copy()
    es_geoshape['type'] = es_geoshape['type'].lower()
    return es_geoshape


@dataclass
class CaseOwnerUpdate:
    case_id: str
    owner_id: str
    related_case_ids: list = field(default_factory=list)

    @classmethod
    def from_case_to_owner_id_dict(cls, case_to_owner_id):
        result = []
        for case_id, owner_id in case_to_owner_id.items():
            result.append(cls(case_id=case_id, owner_id=owner_id))
        return result

    @classmethod
    def total_cases_count(cls, case_owner_updates):
        count = len(case_owner_updates)
        for case_owner_update in case_owner_updates:
            count += len(case_owner_update.related_case_ids)
        return count

    @classmethod
    def to_dict(cls, case_owner_updates):
        return [asdict(obj) for obj in case_owner_updates]


def update_cases_owner(domain, case_owner_updates_dict):
    for case_owner_update in case_owner_updates_dict:
        case_blocks = []
        cases_to_updates = [case_owner_update['case_id']] + case_owner_update['related_case_ids']
        for case_id in cases_to_updates:
            case_blocks.append(
                CaseBlock(
                    create=False,
                    case_id=case_id,
                    owner_id=case_owner_update['owner_id']
                ).as_text()
            )
        submit_case_blocks(
            case_blocks=case_blocks,
            domain=domain,
            device_id=__name__ + '.update_cases_owners'
        )


class CeleryTaskTracker(object):
    """
    Simple Helper class using redis to track if a celery task was requested and is not completed yet.
    """

    def __init__(self, task_key, message_key=None):
        self.task_key = task_key
        self.message_key = message_key
        self._client = get_redis_client()

    def mark_requested(self, timeout=ONE_DAY):
        # Timeout here is just a fail safe mechanism in case task is not processed by Celery
        # due to unexpected circumstances
        self._client.set(self.task_key, 'ACTIVE', timeout=timeout)

    def is_active(self):
        return self._client.has_key(self.task_key)

    def mark_completed(self):
        self.clear_message()
        return self._client.delete(self.task_key)

    def get_message(self):
        return self._client.get(self.message_key)

    def set_message(self, message, timeout=ONE_DAY * 3):
        return self._client.set(self.message_key, message, timeout=timeout)

    def clear_message(self):
        return self._client.delete(self.message_key)
