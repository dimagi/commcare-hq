import logging
from corehq.apps.commtrack.helpers import make_supply_point
from corehq.apps.commtrack.models import Program, SupplyPointCase, Product
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import Location
from custom.openlmis.api import OpenLMISEndpoint
from custom.openlmis.exceptions import BadParentException, OpenLMISAPIException


def _apply_updates(doc, update_dict):
    # updates the doc with items from the dict
    # returns whether or not any updates were made
    should_save = False
    for key, value in update_dict.items():
        if getattr(doc, key, None) != value:
            setattr(doc, key, value)
            should_save = True
    return should_save


def bootstrap_domain(domain):
    project = Domain.get_by_name(domain)
    endpoint = OpenLMISEndpoint.from_config(project.commtrack_settings.openlmis_config)
    for f in endpoint.get_all_facilities():
        try:
            sync_facility_to_supply_point(domain, f)
        except OpenLMISAPIException, e:
            logging.exception('Problem syncing facility %s' % f.code)

    for program in endpoint.get_all_programs(include_products=True):
        sync_openlmis_program(domain, program)



def get_supply_point(domain, facility_or_code):
    facility_code = facility_or_code if isinstance(facility_or_code, basestring) else facility_or_code.code
    return SupplyPointCase.view('hqcase/by_domain_external_id',
        key=[domain, facility_code],
        reduce=False,
        include_docs=True,
    ).one()


def sync_facility_to_supply_point(domain, facility):
    supply_point = get_supply_point(domain, facility)
    facility_dict = {
        'domain': domain,
        'location_type': facility.type,
        'external_id': facility.code,
        'name': facility.name,
        'site_code': facility.code,  # todo: do they have a human readable code?
        'latitude': facility.latitude,
        'longitude': facility.longitude,
    }
    parent_sp = None
    if facility.parent_id:
        parent_sp = get_supply_point(domain, facility.parent_id)
        if not parent_sp:
            raise BadParentException('No matching supply point with code %s found' % facility.parent_id)

    if supply_point is None:
        if parent_sp:
            facility_dict['parent'] = parent_sp.location

        facility_loc = Location(**facility_dict)
        facility_loc.save()
        return make_supply_point(domain, facility_loc)
    else:
        facility_loc = supply_point.location
        if parent_sp and facility_loc.parent_id != parent_sp.location._id:
            raise BadParentException('You are trying to move a location. This is currently not supported.')

        should_save = _apply_updates(facility_loc, facility_dict)
        if should_save:
            facility_loc.save()

        return supply_point


def get_product(domain, lmis_product):
    return Product.get_by_code(domain, lmis_product.code)


def get_program(domain, lmis_program):
    # todo
    return None


def sync_openlmis_program(domain, lmis_program):
    program = get_program(domain, lmis_program)
    if program is None:
        program = Program(domain=domain)
    else:
        # currently impossible
        raise NotImplementedError('updating existing programs is not yet supported')
    program.name = lmis_program.name
    program.code = lmis_program.code
    program.save()
    if lmis_program.products:
        for lmis_product in lmis_program.products:
            sync_openlmis_product(domain, program, lmis_product)
    return program


def sync_openlmis_product(domain, program, lmis_product):
    product = get_product(domain, lmis_product)
    product_dict = {
        'domain': domain,
        'name': lmis_product.name,
        'code': lmis_product.code,
        'unit': str(lmis_product.unit),
        'description': lmis_product.description,
        'category': lmis_product.category,
        'program_id': program._id,

    }
    if product is None:
        product = Product(**product_dict)
        product.save()
    else:
        if _apply_updates(product, product_dict):
            product.save()
    return product


def supply_point_to_json(supply_point):
    base = {
        'agentCode': supply_point.location.site_code,
        'agentName': supply_point.name,
        'active': not supply_point.closed,
    }
    if supply_point.location.parent:
        base['parentFacilityCode'] = supply_point.location.parent.external_id

    # todo phone number
    return base


def sync_supply_point_to_openlmis(supply_point, openlmis_endpoint, create=True):
    """
    https://github.com/OpenLMIS/documents/blob/master/4.1-CreateVirtualFacility%20API.md
    {
        "agentCode":"A2",
        "agentName":"AgentVinod",
        "parentFacilityCode":"F10",
        "phoneNumber":"0099887766",
        "active":"true"
    }
    """
    json_sp = supply_point_to_json(supply_point)
    if create:
        return openlmis_endpoint.create_virtual_facility(json_sp)
    else:
        return openlmis_endpoint.update_virtual_facility(supply_point.external_id, json_sp)


def submit_requisition(requisition, openlmis_endpoint):
    return openlmis_endpoint.submit_requisition(requisition)