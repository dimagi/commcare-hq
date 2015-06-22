from couchdbkit import ResourceNotFound


def get_open_requisition_case_ids_for_supply_point_id(domain, supply_point_id):
    from corehq.apps.commtrack.models import RequisitionCase
    return [r['id'] for r in RequisitionCase.get_db().view(
        'commtrack/requisitions',
        endkey=[domain, supply_point_id, 'open'],
        startkey=[domain, supply_point_id, 'open', {}],
        reduce=False,
        descending=True,
    )]


def get_open_requisition_case_ids_for_location(domain, location_id):
    """
    For a given location, return the IDs of all open requisitions
    at that location.

    """
    from corehq.apps.locations.models import Location
    try:
        sp_id = Location.get(location_id).linked_supply_point()._id
    except ResourceNotFound:
        return []

    return get_open_requisition_case_ids_for_supply_point_id(domain, sp_id)


def get_supply_point_ids_in_domain_by_location(domain):
    """
    Returns a dict that maps from associated location id's
    to supply point id's for all supply point cases in the passed
    domain.
    """
    from corehq.apps.commtrack.models import SupplyPointCase
    return {
        row['key'][1]: row['id'] for row in SupplyPointCase.get_db().view(
            'commtrack/supply_point_by_loc',
            startkey=[domain],
            endkey=[domain, {}],
        )
    }


def get_supply_points_json_in_domain_by_location(domain):
    from corehq.apps.commtrack.models import SupplyPointCase
    results = SupplyPointCase.get_db().view(
        'commtrack/supply_point_by_loc',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=True,
    )

    for result in results:
        location_id = result['key'][-1]
        case = result['doc']
        yield location_id, case


def get_supply_point_case_by_location_id(domain, location_id):
    from corehq.apps.commtrack.models import SupplyPointCase
    return SupplyPointCase.view(
        'commtrack/supply_point_by_loc',
        key=[domain, location_id],
        include_docs=True,
        classes={'CommCareCase': SupplyPointCase},
    ).one()


def get_supply_point_case_by_location(location):
    return get_supply_point_case_by_location_id(location.domain, location._id)
