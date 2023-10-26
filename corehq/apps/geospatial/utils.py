from jsonobject.exceptions import BadValueError

from couchforms.geopoint import GeoPoint

from corehq.apps.hqcase.case_helper import CaseHelper
from corehq.apps.users.models import CommCareUser
from corehq.util.quickcache import quickcache

from .models import GeoConfig


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


def set_case_gps_property(domain, case_data):
    location_prop_name = get_geo_case_property(domain)
    helper = CaseHelper(domain=domain, case_id=case_data['id'])
    case_data = {
        'properties': {
            location_prop_name: _format_coordinates(case_data['lat'], case_data['lon'])
        }
    }

    helper.update(case_data)


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
