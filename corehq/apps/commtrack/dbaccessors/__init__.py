

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
