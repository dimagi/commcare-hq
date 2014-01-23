import logging
from couchdbkit import ResourceNotFound
from casexml.apps.stock.consumption import compute_consumption, from_ts
from pillowtop.listener import BasicPillow
from couchforms.models import XFormInstance
import collections
from corehq.apps.commtrack.models import SupplyPointProductCase

pillow_logging = logging.getLogger("pillowtop")


class ConsumptionRatePillow(BasicPillow):
    document_class = XFormInstance
    couch_filter = 'commtrack/stock_reports'

    def change_transform(self, doc_dict):
        txs = doc_dict['form'].get('transaction', [])
        if not isinstance(txs, collections.Sequence):
            txs = [txs]
        touched_products = set(tx['product_entry'] for tx in txs)

        for case_id in touched_products:
            try:
                case = SupplyPointProductCase.get(case_id)
            except ResourceNotFound:
                # maybe the case was deleted. for now we don't care about this
                pillow_logging.info('skipping commtrack update for deleted case %s' % case_id)
            else:
                rate = compute_consumption(case_id, case.product,
                                           from_ts(doc_dict['received_on']))
                set_computed(case, 'consumption_rate', rate)
                case.save()

# TODO: biyeun might have better framework code for doing this
def set_computed(case, key, val):
    NAMESPACE = 'commtrack'
    if not NAMESPACE in case.computed_:
        case.computed_[NAMESPACE] = {}
    case.computed_[NAMESPACE][key] = val
