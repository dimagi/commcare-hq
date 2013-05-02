from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save, cases_received
from corehq.apps.commtrack import const
from corehq.apps.commtrack.const import is_commtrack_form
from corehq.apps.commtrack.models import RequisitionCase, SupplyPointProductCase
from corehq.apps.locations.models import Location


def attach_locations(sender, xform, cases, **kwargs):
    """
    Given a received form and cases, update the location of that form to the location
    of its cases (if they have one).
    """

    # todo: this won't change locations if you are trying to do that via XML.
    # this is mainly just a performance thing so you don't have to do extra lookups
    # every time you touch a case

    if is_commtrack_form(xform) and cases:
        found_loc = None
        for case in cases:
            loc = None
            if not case.location_:
                if case.type == const.SUPPLY_POINT_CASE_TYPE:
                    loc_id = getattr(case, 'location_id', None)
                    if loc_id:
                        loc = Location.get(loc_id)
                        case.bind_to_location(loc)

                elif case.type == const.SUPPLY_POINT_PRODUCT_CASE_TYPE:
                    wrapped_case = SupplyPointProductCase.wrap(case._doc)
                    sp = wrapped_case.get_supply_point_case()
                    if sp and sp.location_:
                        loc = sp.location_
                        case.location_ = loc

                elif case.type == const.REQUISITION_CASE_TYPE:
                    req = RequisitionCase.wrap(case._doc)
                    prod = req.get_product_case()
                    if prod and prod.location_ and prod.location_ != case.location_:
                        case.location_ = prod.location_
                        case.save()

            if loc and found_loc and loc != found_loc:
                raise Exception(
                    'Submitted a commtrack case with multiple locations in a single form. '
                    'This is currently not allowed.'
                )
            found_loc = loc

        case = cases[0]
        if case.location_ is not None:
            # should probably store this in computed_
            xform.location_ = list(case.location_)

cases_received.connect(attach_locations)
