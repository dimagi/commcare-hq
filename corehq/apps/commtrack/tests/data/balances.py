from datetime import datetime
import uuid
from xml.etree import ElementTree
from dimagi.utils.parsing import json_format_datetime
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xml import V2
from corehq.apps.commtrack import const


def long_date(timestamp=None):
    if not timestamp:
        timestamp = datetime.utcnow()
    return json_format_datetime(timestamp)


def balance_ota_block(sp, section_id, product_amounts, datestring):
    return """
        <ns0:balance xmlns:ns0="http://commcarehq.org/ledger/v1" xmlns="http://openrosa.org/http/response" date="{long_date}" entity-id="{sp_id}" section-id="{section_id}">
            {product_block}
        </ns0:balance>
    """.format(
        sp_id=sp._id,
        section_id=section_id,
        long_date=datestring,
        product_block=products_xml(product_amounts),
    )


def submission_wrap(instance_id, products, user, sp, sp2, insides, timestamp=None):
    insides = insides() if callable(insides) else insides
    return ("""<?xml version="1.0" ?>
        <data uiVersion="1" version="33" name="New Form" xmlns="http://commtrack.org/test_form_submission">
            <products>{product0} {product1} {product2}</products>
            <meta>
                <deviceID>351746051189879</deviceID>
                <timeStart>2013-12-10T17:08:46.215-05</timeStart>
                <timeEnd>2013-12-10T17:08:57.887-05</timeEnd>
                <username>{username}</username>
                <userID>{user_id}</userID>
                <instanceID>{instance_id}</instanceID>
                <appVersion>CommTrack Unit tests</appVersion>
            </meta>
            <num_products>3</num_products>
            <cur_products>3</cur_products>
            %s
        </data>
    """ % insides).format(
        sp_id=sp._id,
        sp2_id=sp2._id,
        product0=products[0]._id,
        product1=products[1]._id,
        product2=products[2]._id,
        user_id=user._id,
        instance_id=instance_id,
        username=user.username,
        long_date=long_date(timestamp),
    )


def products_xml(product_amount_tuples):
    return ''.join([
        '<ns0:entry id="{id}" quantity="{quantity}" />'.format(
            id=p, quantity=amt,
        ) for p, amt in product_amount_tuples
    ])


def _enumerated_products_xml(product_amount_tuples, section_id='stock'):
    return ''.join([
        """
            <ns0:entry id="{id}">
                <value section-id='{section_id}' quantity="{quantity}"/>
            </ns0:entry>
        """.format(id=p, section_id=section_id, quantity=amt) for p, amt in product_amount_tuples
    ])


def balance_submission(product_amounts, section_id='stock'):
    return """
        <ns0:balance xmlns:ns0="http://commcarehq.org/ledger/v1" date="{long_date}" entity-id="{sp_id}" section-id="%(section_id)s">
            %(product_block)s
        </ns0:balance>
    """ % {'product_block': products_xml(product_amounts), 'section_id': section_id}

def balance_enumerated(product_amounts, section_id='stock'):
    return """
        <ns0:balance xmlns:ns0="http://commcarehq.org/ledger/v1" date="{long_date}" entity-id="{sp_id}">
            %(product_block)s
        </ns0:balance>
    """ % {'product_block': _enumerated_products_xml(product_amounts, section_id), 'section_id': section_id}


def transfer_dest_only(product_amounts):
    return """
        <receipts>
            <ns0:transfer xmlns:ns0="http://commcarehq.org/ledger/v1" dest="{sp_id}" date="{long_date}" section-id="stock">
                %(product_block)s
            </ns0:transfer>
        </receipts>
    """ % {'product_block': products_xml(product_amounts)}


def transfer_source_only(product_amounts):
    return """
        <losses>
            <ns0:transfer xmlns:ns0="http://commcarehq.org/ledger/v1" src="{sp_id}" date="{long_date}" section-id="stock">
                %(product_block)s
            </ns0:transfer>
        </losses>
    """ % {'product_block': products_xml(product_amounts)}


def transfer_both(product_amounts):
    # TODO Does this get wrapped in something? receipts?
    return """
        <ns0:transfer xmlns:ns0="http://commcarehq.org/ledger/v1" src="{sp_id}" dest="{sp2_id}" date="{long_date}" section-id="stock">
            %(product_block)s
        </ns0:transfer>
    """ % {'product_block': products_xml(product_amounts)}


def receipts_enumerated(product_amounts):
    return """
        <receipts>
            <ns0:transfer xmlns:ns0="http://commcarehq.org/ledger/v1" dest="{sp_id}" date="{long_date}">
                %(product_block)s
            </ns0:transfer>
        </receipts>
    """ % {'product_block': _enumerated_products_xml(product_amounts)}


def create_requisition_xml(product_amounts):
    req_id = uuid.uuid4().hex
    req_case_block = ElementTree.tostring(CaseBlock(
        req_id,
        version=V2,
        create=True,
        case_type=const.REQUISITION_CASE_TYPE,
        case_name='Some requisition',
        index={'parent_id': (const.SUPPLY_POINT_CASE_TYPE, '{sp_id}')},
        update={'requisition_status': 'requested'},
    ).as_xml())
    return """
        %(case_block)s
        <ns0:balance xmlns:ns0="http://commcarehq.org/ledger/v1" date="{long_date}" entity-id="%(req_id)s" section-id="ct-requested">
            %(product_block)s
        </ns0:balance>
    """ % {'req_id': req_id, 'case_block': req_case_block, 'product_block': products_xml(product_amounts)}


def create_fulfillment_xml(original_requisition, product_amounts):
    req_id = original_requisition._id
    req_case_block = ElementTree.tostring(CaseBlock(
        req_id,
        version=V2,
        case_type=const.FULFILLMENT_CASE_TYPE,
        case_name='Some requisition',
        index={'parent_id': (const.REQUISITION_CASE_TYPE, '{sp_id}')},
        update={'requisition_status': 'fulfilled'},
    ).as_xml())
    # TODO: needs a source supply point
    return """
        {case_block}
        <ns0:transfer xmlns:ns0="http://commcarehq.org/ledger/v1" dest="{req_id}" date="{long_date}" section-id="stock">
            {product_block}
        </ns0:transfer>
        <ns0:balance xmlns:ns0="http://commcarehq.org/ledger/v1" date="{long_date}" entity-id="{req_id}" section-id="ct-fulfilled">
            {product_block}
        </ns0:balance>
    """.format(
        req_id=req_id,
        case_block=req_case_block,
        product_block=products_xml(product_amounts),
        long_date=long_date()
    )

def create_received_xml(original_requisition, product_amounts):
    req_id = original_requisition._id
    req_case_block = ElementTree.tostring(CaseBlock(
        req_id,
        version=V2,
        close=True,
        case_type=const.RECEIVED_CASE_TYPE,
        case_name='Some requisition',
        index={'parent_id': (const.REQUISITION_CASE_TYPE, '{sp_id}')},
        update={'requisition_status': 'received'},
    ).as_xml())
    return """
        {case_block}
        <ns0:transfer xmlns:ns0="http://commcarehq.org/ledger/v1" dest="{dest_id}" date="{long_date}" src="{req_id}" section-id="stock">
            {product_block}
        </ns0:transfer>
    """.format(
        req_id=req_id,
        case_block=req_case_block,
        product_block=products_xml(product_amounts),
        dest_id=original_requisition.indices[0].referenced_id,
        long_date=long_date()
    )

def balance_first(balance_amounts, transfer_amounts):
    return '%s%s' % (balance_submission(balance_amounts), transfer_dest_only(transfer_amounts))

def transfer_first(transfer_amounts, balance_amounts):
    return '%s%s' % (transfer_dest_only(transfer_amounts), balance_submission(balance_amounts))
