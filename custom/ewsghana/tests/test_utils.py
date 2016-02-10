from corehq.apps.locations.models import Location
from corehq.apps.products.models import SQLProduct


def assign_products_to_locations(location, products_codes_list):
    sql_location = location.sql_location
    sql_location.products = SQLProduct.objects.filter(code__in=products_codes_list, domain=sql_location.domain)
    sql_location.save()


def create_test_locations(domain):
    country = Location(name='national', site_code='ghana', location_type='country', domain=domain)
    country.save()

    crms = Location(
        name='Central Regional Medical Store',
        site_code='crms',
        location_type='country',
        domain=domain
    )
    crms.save()

    test_region = Location(
        name='Test Region',
        site_code='testregion',
        location_type='region',
        domain=domain,
        parent=country
    )
    test_region.save()

    test_region2 = Location(
        name='Test Region2',
        site_code='testregion2',
        location_type='region',
        domain=domain,
        parent=country
    )
    test_region2.save()

    rsp = Location(
        name='Test Regional Medical Store',
        site_code='rsp',
        location_type='Regional Medical Store',
        domain=domain,
        parent=test_region2
    )
    rsp.save()
    assign_products_to_locations(rsp, ["ad", "al", "mc", "ng", "mg"])

    rsp2 = Location(
        name='Test Regional Medical Store',
        site_code='rsp2',
        location_type='Regional Medical Store',
        domain=domain,
        parent=test_region2
    )
    rsp2.save()
    assign_products_to_locations(rsp2, ["ad", "al"])

    test_district = Location(
        name='Test District',
        site_code='testdistrict',
        location_type='district',
        domain=domain,
        parent=test_region
    )
    test_district.save()

    test_facility = Location(
        name='Active Test hospital',
        site_code='tsactive',
        location_type='Hospital',
        domain=domain,
        parent=test_district
    )
    test_facility.save()
    assign_products_to_locations(test_facility, ["ad", "al"])
