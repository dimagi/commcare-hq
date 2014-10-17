import fluff
from couchforms.models import XFormInstance
from fluff.filters import ORFilter, ANDFilter
from casexml.apps.case.models import CommCareCase
from corehq.fluff.calculators.xform import FormPropertyFilter
from custom.tdh import TDH_DOMAINS


class TDHFluff(fluff.IndicatorDocument):
    document_class = XFormInstance

    domains = TDH_DOMAINS
    save_direct_to_sql = True

TDHFluffPillow = TDHFluff.pillow()