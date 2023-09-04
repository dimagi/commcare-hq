from corehq.apps.data_dictionary.models import CaseProperty
from corehq.apps.geospatial.models import GeoConfig


def get_geo_case_property(domain):
    try:
        config = GeoConfig.objects.get(domain=domain)
    except GeoConfig.DoesNotExist:
        config = GeoConfig()
    return config.case_location_property_name


def is_gps_case_property_deprecated(domain, prop_name):
    return bool(
        CaseProperty.objects.filter(
            case_type__domain=domain,
            name=prop_name,
            deprecated=True,
            data_type=CaseProperty.DataType.GPS,
        ).count()
    )
