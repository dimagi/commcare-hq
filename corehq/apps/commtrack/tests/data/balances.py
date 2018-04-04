from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple
from datetime import datetime
from dimagi.utils.parsing import json_format_datetime

SohReport = namedtuple('SohReport', 'section_id product_id amount')


def balance_ota_block(sp, section_id, soh_reports, datestring):
    return """
        <ns0:balance xmlns:ns0="http://commcarehq.org/ledger/v1" xmlns="http://openrosa.org/http/response" date="{long_date}" entity-id="{sp_id}" section-id="{section_id}">
            {product_block}
        </ns0:balance>
    """.format(
        sp_id=sp.case_id,
        section_id=section_id,
        long_date=datestring,
        product_block=products_xml([(report.product_id, report.amount) for report in soh_reports]),
    )


def submission_wrap(instance_id, products, user, sp_id, sp2_id, insides, timestamp=None,
                    date_formatter=json_format_datetime, device_id=None):
    timestamp = timestamp or datetime.utcnow()
    date_string = date_formatter(timestamp)
    insides = insides() if callable(insides) else insides
    return ("""<?xml version="1.0" ?>
        <data uiVersion="1" version="33" name="New Form" xmlns="http://commtrack.org/test_form_submission">
            <products>{product0} {product1} {product2}</products>
            <meta>
                <deviceID>{device_id}</deviceID>
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
        sp_id=sp_id,
        sp2_id=sp2_id,
        product0=products[0]._id,
        product1=products[1]._id,
        product2=products[2]._id,
        user_id=user._id,
        instance_id=instance_id,
        username=user.username,
        long_date=date_string,
        device_id=device_id if device_id is not None else '',
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


def balance_first(balance_amounts, transfer_amounts):
    return '%s%s' % (balance_submission(balance_amounts), transfer_dest_only(transfer_amounts))


def transfer_first(transfer_amounts, balance_amounts):
    return '%s%s' % (transfer_dest_only(transfer_amounts), balance_submission(balance_amounts))
