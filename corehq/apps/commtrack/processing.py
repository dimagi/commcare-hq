import logging
from casexml.apps.case.const import CASE_ACTION_COMMTRACK
from casexml.apps.case.xform import is_device_report
from casexml.apps.stock.const import COMMTRACK_REPORT_XMLNS
from dimagi.utils.decorators.log_exception import log_exception
from corehq.apps.commtrack.models import CommtrackConfig, NewStockReport
from dimagi.utils.couch.loosechange import map_reduce
from corehq.apps.commtrack.util import wrap_commtrack_case
from casexml.apps.case.models import CommCareCaseAction, CommCareCase
from casexml.apps.case.xml.parser import AbstractAction


logger = logging.getLogger('commtrack.incoming')

COMMTRACK_LEGACY_REPORT_XMLNS = 'http://commtrack.org/legacy/stock_report'

def process_stock_signal_catcher(sender, xform, config=None, **kwargs):
    return process_stock(xform)

@log_exception()
def process_stock(xform):
    """
    process the commtrack xml constructs in an incoming submission
    """
    if is_device_report(xform):
        return

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
    try:
        relevant_cases = [wrap_commtrack_case(result['doc']) for result in
                          CommCareCase.get_db().view('_all_docs',
                                                     keys=list(set(k[0] for k in grouped_tx)),
                                                     include_docs=True)]
    except KeyError:
        raise Exception("Cannot find case matching supplied entity id")

    user_id = xform.form['meta']['userID']
    submit_time = xform['received_on']

    # touch every case for proper ota restore logic syncing to be preserved
    for case in relevant_cases:
        case_action = CommCareCaseAction.from_parsed_action(
            submit_time, user_id, xform, AbstractAction(CASE_ACTION_COMMTRACK)
        )
        # hack: clear the sync log id so this modification always counts
        # since consumption data could change server-side
        case_action.sync_log_id = ''
        case.actions.append(case_action)
        case.save()

    # create the django models
    for report in stock_reports:
        report.create_models()

    # TODO make this a signal
    from corehq.apps.commtrack.signals import send_notifications, raise_events
    send_notifications(xform, relevant_cases)
    raise_events(xform, relevant_cases)

def unpack_commtrack(xform, config):
    xml = xform.get_xml_element()

    def commtrack_nodes(node):
        for child in node:
            if child.tag.startswith('{%s}' % COMMTRACK_REPORT_XMLNS):
                yield child
            else:
                for e in commtrack_nodes(child):
                    yield e

    for elem in commtrack_nodes(xml):
        yield NewStockReport.from_xml(xform, config, elem)
