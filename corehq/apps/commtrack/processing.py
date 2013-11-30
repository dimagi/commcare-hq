import logging
from dimagi.utils.logging import log_exception
from corehq.apps.commtrack.models import CommtrackConfig, StockTransaction
from corehq.apps.commtrack import const
import collections

logger = logging.getLogger('commtrack.incoming')

# FIXME this decorator is causing me bizarre import issues
#@log_exception()
def process_stock(sender, xform, config=None, **kwargs):
    """process the commtrack xml constructs in an incoming submission"""
    domain = xform.domain

    config = CommtrackConfig.for_domain(domain)
    transactions = list(unpack_commtrack(xform, config))

    print transactions

    return
    #####

def asdf():
    user_id, transactions = unpack_transactions(root, config)
    transactions = list(normalize_transactions(transactions))

    def get_transactions(all_tx, type_filter):
        """get all the transactions of the relevant type (filtered by type_filter),
        grouped by product (returns a dict of 'product subcase id' => list of transactions),
        with each set of transactions sorted in the correct order for processing
        """
        return map_reduce(lambda tx: [(tx.case_id,)],
                          lambda v: sorted(v, key=lambda tx: tx.priority_order), # important!
                          data=filter(type_filter, all_tx),
                          include_docs=True)

    # split transactions by type and product
    stock_transactions = get_transactions(transactions, lambda tx: tx.category == 'stock')
    requisition_transactions = get_transactions(transactions, lambda tx: tx.category == 'requisition')

    case_ids = list(set(itertools.chain(*[tx.get_case_ids() for tx in transactions])))
    cases = dict((c._id, c) for c in CommCareCase.view('_all_docs', keys=case_ids, include_docs=True))

    # TODO: code to auto generate / update requisitions from transactions if
    # project is configured for that.

    # TODO: when we start receiving commcare-submitted reports, we should be using a server time rather
    # than relying on timeStart (however timeStart is set to server time for reports received via sms)
    submit_time = root.find('.//%s' % _('timeStart', META_XMLNS)).text
    post_processed_transactions = list(transactions)
    for product_id, product_case in cases.iteritems():
        stock_txs = stock_transactions.get(product_id, [])
        if stock_txs:
            case_block, reconciliations = process_product_transactions(user_id, submit_time, product_case, stock_txs)
            root.append(case_block)
            post_processed_transactions.extend(reconciliations)

        req_txs = requisition_transactions.get(product_id, [])
        if req_txs and config.requisitions_enabled:
            req = RequisitionState.from_transactions(user_id, product_case, req_txs)
            case_block = etree.fromstring(req.to_xml())
            root.append(case_block)
    replace_transactions(root, post_processed_transactions)

    submission = etree.tostring(root)
    logger.debug('submitting: %s' % submission)



    """
    get da stock transactions out of the form
    convert to stocktransaction objects

    operate on stocktx thereon

    group stocktx by (loc, product)

    fetch subcases

    for each subcase, order tx appropriately

    update and reconcile stock (case blocks as output)

    submit case update form
    """


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
