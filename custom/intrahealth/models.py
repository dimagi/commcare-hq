import fluff
from couchforms.models import XFormInstance
from custom.intrahealth import INTRAHEALTH_DOMAINS, report_calcs


def flat_field(fn):
    def getter(item):
        return unicode(fn(item) or "")
    return fluff.FlatField(getter)

class CouvertureFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    domains = INTRAHEALTH_DOMAINS
    group_by = ('domain', 'date', 'location_id')
    save_direct_to_sql = True


    registered = report_calcs.PPSRegistered()
    planned = report_calcs.PPSPlaned()
    visited = report_calcs.PPSVisited()
    submitted = report_calcs.PPSSubmitted()

CouvertureFluffPillow = CouvertureFluff.pillow()