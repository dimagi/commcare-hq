import logging
from dimagi.utils.logging import log_exception
from corehq.apps.commtrack.models import CommtrackConfig, StockTransaction, SupplyPointCase
from corehq.apps.commtrack import const
import collections
from dimagi.utils.couch.loosechange import map_reduce

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.xml import V2
from xml import etree as legacy_etree

logger = logging.getLogger('commtrack.incoming')

# FIXME this decorator is causing me bizarre import issues
#@log_exception()
def process_stock(sender, xform, config=None, **kwargs):
    """process the commtrack xml constructs in an incoming submission"""
    domain = xform.domain

    config = CommtrackConfig.for_domain(domain)
    transactions = list(unpack_commtrack(xform, config))
    # omitted: normalize_transactions (used for bulk requisitions?)
    if not transactions:
        return

    grouped_tx = map_reduce(lambda tx: [((tx.case_id, tx.product_id),)],
                            lambda v: sorted(v, key=lambda tx: (tx.timestamp, tx.processing_order)),
                            data=transactions,
                            include_docs=True)

    supply_point_cases = SupplyPointCase.view('_all_docs',
                                              keys=list(set(k[0] for k in grouped_tx)),
                                              include_docs=True)
    supply_point_product_subcases = dict((sp._id, product_subcases(sp)) for sp in supply_point_cases)

    submit_time = xform['received_on']
    post_processed_transactions = list(transactions)
    for (supply_point_id, product_id), txs in grouped_tx.iteritems():
        subcase = supply_point_product_subcases[supply_point_id][product_id]

        print subcase

        """
            case_block, reconciliations = process_product_transactions(user_id, submit_time, product_case, stock_txs)
            root.append(case_block)
            post_processed_transactions.extend(reconciliations)
        """

        #req_txs = requisition_transactions.get(product_id, [])
        #if req_txs and config.requisitions_enabled:
        #    req = RequisitionState.from_transactions(user_id, product_case, req_txs)
        #    case_block = etree.fromstring(req.to_xml())
        #    root.append(case_block)
    replace_transactions(root, post_processed_transactions)


    # argh, need to make a submission here again

    submission = etree.tostring(root)
    logger.debug('submitting: %s' % submission)




    return
    #####

    """
    x get da stock transactions out of the form
    x convert to stocktransaction objects

    operate on stocktx thereon

    x group stocktx by (loc, product)

    x fetch subcases

    for each subcase, order tx appropriately

    update and reconcile stock (case blocks as output)

    submit case update form
    """



# TODO retire this with move to new data model
def product_subcases(supply_point):
    """given a supply point, return all the sub-cases for each product stocked at that supply point
    actually returns a mapping: product doc id => sub-case id
    ACTUALLY returns a dict that will create non-existent product sub-cases on demand
    """
    from helpers import make_supply_point_product

    product_subcase_uuids = [ix.referenced_id for ix in supply_point.reverse_indices if ix.identifier == const.PARENT_CASE_REF]
    product_subcases = CommCareCase.view('_all_docs', keys=product_subcase_uuids, include_docs=True)
    product_subcase_mapping = dict((subcase.dynamic_properties().get('product'), subcase._id) for subcase in product_subcases)

    def create_product_subcase(product_uuid):
        return make_supply_point_product(supply_point, product_uuid)._id

    class DefaultDict(dict):
        """similar to collections.defaultdict(), but factory function has access
        to 'key'
        """
        def __init__(self, factory, *args, **kwargs):
            super(DefaultDict, self).__init__(*args, **kwargs)
            self.factory = factory

        def __getitem__(self, key):
            if key in self:
                val = self.get(key)
            else:
                val = self.factory(key)
                self[key] = val
            return val

    return DefaultDict(create_product_subcase, product_subcase_mapping)

def unpack_commtrack(xform, config):
    global_context = {
        'timestamp': xform.received_on,
    }

    def commtrack_nodes(data):
        for tag, nodes in data.iteritems():
            for node in (nodes if isinstance(nodes, collections.Sequence) else [nodes]):
                if not hasattr(node, '__iter__'):
                    continue
                if node.get('@xmlns', data['@xmlns']) == const.COMMTRACK_REPORT_XMLNS:
                    yield (tag, node)
    for elem in commtrack_nodes(xform.form):
        # FIXME deal with requisitions later
        tag, node = elem
        products = node['product']
        if not isinstance(products, collections.Sequence):
            products = [products]
        for prod_entry in products:
            yield StockTransaction.from_xml(config, global_context, tag, node, prod_entry)
