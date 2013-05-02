from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from corehq.apps.commtrack import const
from corehq.apps.commtrack.models import RequisitionCase


def attach_location(sender, case, **kwargs):
    if case.type == const.REQUISITION_CASE_TYPE:
        req = RequisitionCase.wrap(case._doc)
        prod = req.get_product_case()
        if prod and prod.location_ and prod.location_ != case.location_:
            case.location_ = prod.location_
            case.save()

case_post_save.connect(attach_location, CommCareCase)
