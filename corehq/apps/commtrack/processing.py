import logging
from casexml.apps.stock.const import TRANSACTION_SUBTYPE_INFERRED, COMMTRACK_REPORT_XMLNS
from dimagi.utils.decorators.log_exception import log_exception
from corehq.apps.commtrack.models import CommtrackConfig, StockTransaction, NewStockReport
from corehq.apps.commtrack import const
from dimagi.utils.couch.loosechange import map_reduce
from corehq.apps.commtrack.util import wrap_commtrack_case
from casexml.apps.case.models import CommCareCaseAction, CommCareCase
from casexml.apps.case.xml.parser import AbstractAction

from lxml import etree


logger = logging.getLogger('commtrack.incoming')

COMMTRACK_LEGACY_REPORT_XMLNS = 'http://commtrack.org/legacy/stock_report'

@log_exception()
def process_stock(sender, xform, config=None, **kwargs):
    """
    process the commtrack xml constructs in an incoming submission
    """
    domain = xform.domain

    config = CommtrackConfig.for_domain(domain)

    # these are the raw stock report objects from the xml
    stock_reports = list(unpack_commtrack(xform, config))
    # flattened transaction list spanning all stock reports in the form
    transactions = [t for r in stock_reports for t in r.transactions]
    # omitted: normalize_transactions (used for bulk requisitions?)

    if not transactions:
        return

    # transactions grouped by case/product id
    grouped_tx = map_reduce(lambda tx: [((tx.case_id, tx.product_id),)],
                            lambda v: sorted(v, key=lambda tx: tx.timestamp),
                            data=transactions,
                            include_docs=True)

    # list of cases that had stock reports in the form, properly wrapped by case type
    relevant_cases = [wrap_commtrack_case(result['doc']) for result in
                      CommCareCase.get_db().view('_all_docs',
                                                 keys=list(set(k[0] for k in grouped_tx)),
                                                 include_docs=True)]
    user_id = xform.form['meta']['userID']
    submit_time = xform['received_on']

    # touch every case for proper ota restore logic syncing to be preserved
    # todo: confirm this is necessary
    for case in relevant_cases:
        case_action = CommCareCaseAction.from_parsed_action(submit_time, user_id, xform, AbstractAction('commtrack'))
        case.actions.append(case_action)
        case.save()

    def _is_stockonhand_txn(txn):
        return txn.section_id == 'stock'

    # create the django models
    for report in stock_reports:
        report.create_models()

def unpack_commtrack(xform, config):
    xml = etree.fromstring(xform.get_xml())

    def commtrack_nodes(node):
        for child in node:
            if child.tag.startswith('{%s}' % COMMTRACK_REPORT_XMLNS):
                yield child
            else:
                for e in commtrack_nodes(child):
                    yield e

    for elem in commtrack_nodes(xml):
        yield NewStockReport.from_xml(xform, config, elem)


from couchdbkit.ext.django.schema import *
class LegacyStockTransaction(StockTransaction):
    product_subcase = StringProperty()

    def to_legacy_xml(self, E):
        attr = {}
        if self.subaction == TRANSACTION_SUBTYPE_INFERRED:
            attr['inferred'] = 'true'
        if self.processing_order is not None:
            attr['order'] = str(self.processing_order + 1)

        return E.transaction(
            E.product(self.product_id),
            E.product_entry(self.product_subcase),
            E.action((self.subaction if self.subaction != TRANSACTION_SUBTYPE_INFERRED else None) or self.action),
            E.value(str(self.quantity)),
            **attr
        )
