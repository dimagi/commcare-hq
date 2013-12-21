from datetime import datetime
from dimagi.utils.parsing import json_format_datetime


def long_date():
    return json_format_datetime(datetime.utcnow())


def balances_with_adequate_values(sp, products, datestring=None):
    if datestring is None:
        datestring = long_date()

    return """
        <ns0:balance xmlns:ns0="http://commtrack.org/stock_report" xmlns="http://openrosa.org/http/response" date="{long_date}" entity-id="{sp_id}">
            <ns0:product id="{product0}" quantity="10" />
            <ns0:product id="{product1}" quantity="10" />
            <ns0:product id="{product2}" quantity="10" />
        </ns0:balance>
    """.format(
        sp_id=sp._id,
        long_date=datestring,
        product0=products[0]._id,
        product1=products[1]._id,
        product2=products[2]._id,
    )


def submission_wrap(products, user, sp, sp2, insides):
    insides = insides() if callable(insides) else insides
    return ("""<?xml version="1.0" encoding="UTF-8"?>
        <data uiVersion="1" version="33" name="New Form" xmlns="http://commtrack.org/test_form_submission">
            <products>{product0} {product1} {product2}</products>
            <meta>
                <deviceID>351746051189879</deviceID>
                <timeStart>2013-12-10T17:08:46.215-05</timeStart>
                <timeEnd>2013-12-10T17:08:57.887-05</timeEnd>
                <username>{username}</username>
                <userID>{user_id}</userID>
                <instanceID>398c9e36-b645-4b68-81b6-6957a2d3cf90</instanceID>
                <appVersion>CommCare ODK, version "2.10.1"(28262). App v33. CommCare Version 2.10. Build 28262, built on: November-28-2013</appVersion>
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
        username=user.username,
        long_date=long_date() + 'Z',
    )


def _products_xml(product_amount_tuples):
    return ''.join([
        '<ns0:product index="{i}" id="{id}" quantity="{quantity}" />'.format(
            i=i, id=p, quantity=amt,
        ) for i, (p, amt) in enumerate(product_amount_tuples)
    ])

def balance_submission(product_amounts):
    return """
        <ns0:balance xmlns:ns0="http://commtrack.org/stock_report" date="{long_date}" entity-id="{sp_id}">
            %(product_block)s
        </ns0:balance>
    """ % {'product_block': _products_xml(product_amounts)}


def transfer_dest_only(product_amounts):
    return """
        <receipts>
            <ns0:transfer xmlns:ns0="http://commtrack.org/stock_report" dest="{sp_id}" date="{long_date}">
                %(product_block)s
            </ns0:transfer>
        </receipts>
    """ % {'product_block': _products_xml(product_amounts)}


def transfer_source_only(product_amounts):
    return """
        <losses>
            <ns0:transfer xmlns:ns0="http://commtrack.org/stock_report" src="{sp_id}" date="{long_date}">
                %(product_block)s
            </ns0:transfer>
        </losses>
    """ % {'product_block': _products_xml(product_amounts)}


def transfer_both(product_amounts):
    # TODO Does this get wrapped in something? receipts?
    return """
        <ns0:transfer xmlns:ns0="http://commtrack.org/stock_report" src="{sp_id}" dest="{sp2_id}" date="{long_date}">
            %(product_block)s
        </ns0:transfer>
    """ % {'product_block': _products_xml(product_amounts)}


def transfer_neither():
    return """
        <transfer date="{long_date}">
            <product index="0" id="{product0}" quantity="4" />
            <product index="1" id="{product1}" quantity="1" />
            <product index="2" id="{product2}" quantity="1" />
        </transfer>
    """


def balance_first(balance_amounts, transfer_amounts):
    return '%s%s' % (balance_submission(balance_amounts), transfer_dest_only(transfer_amounts))

def transfer_first(transfer_amounts, balance_amounts):
    return '%s%s' % (transfer_dest_only(transfer_amounts), balance_submission(balance_amounts))
