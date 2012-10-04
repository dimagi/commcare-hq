from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests.util import CaseBlock
from casexml.apps.case.xml import V2
from lxml import etree
from datetime import datetime, date, timedelta

XMLNS = 'http://openrosa.org/commtrack/stock_report'

def process(instance):
    root = etree.fromstring(instance)

    def _(tag, ns=XMLNS):
        return '{%s}%s' % (ns, tag)

    case_ids = [e.text for e in root.findall('.//%s' % _('product_entry'))]
    cases = dict((c._id, c) for c in CommCareCase.view('_all_docs', keys=case_ids, include_docs=True))

    for tx in root.findall(_('transaction')):
        case_id = tx.find(_('product_entry')).text
        tx_data = (
            tx.find(_('action')).text,
            int(tx.find(_('value')).text),
        )
        case_block = process_transaction(tx_data, cases[case_id])
        root.append(case_block)

    print etree.tostring(root, pretty_print=True)

    # submit against case via casexml



def process_transaction(tx, case):
    action, value = tx

    prop = lambda k, default: case.dynamic_properties().get(k, default)
    current_state = {
        'current_stock': prop('current_stock', 0),
        'stocked_out_since': prop('stocked_out_since', None),
    }
    # worry about consumption rates later

    update_stock_info(current_state, action, value)

    # generate case block
    case_update = CaseBlock(
        version=V2,
        case_id=case._id,
        user_id='fixme',
        update=dict((k, str(v)) for k, v in current_state.iteritems())
    ).as_xml()
    # convert xml.etree to lxml
    from xml.etree import ElementTree
    case_update = etree.fromstring(ElementTree.tostring(case_update))

    return case_update

# business logic to reconcile stock reports lives HERE
def update_stock_info(s, action, value):
    if s['stocked_out_since']:
        s['stocked_out_since'] = datetime.strptime(s['stocked_out_since'], '%Y-%m-%d').date()

    # what order should stuff be processed in? if both a stock-on-hand and
    # receipts come in, the order in which applied matters

    if action == 'stockout':
        s['current_stock'] = 0
        s['stocked_out_since'] = date.today() - timedelta(days=value)
    else:

        if action == 'stockonhand':
            s['current_stock'] = value
        elif action == 'receipts':
            s['current_stock'] += value
        elif action == 'consumption':
            s['current_stock'] -= value

        if s['current_stock'] > 0:
            s['stocked_out_since'] = None
        else:
            s['current_stock'] = 0 # handle if negative
            if not s['stocked_out_since']: # handle if stocked out date already set
                s['stocked_out_since'] = date.today()

    if s['stocked_out_since']:
        s['stocked_out_since'] = datetime.strftime(s['stocked_out_since'], '%Y-%m-%d')
    else:
        s['stocked_out_since'] = ''
