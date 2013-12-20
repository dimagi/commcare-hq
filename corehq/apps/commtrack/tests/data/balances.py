from datetime import date, datetime


def long_date():
    return '' # TODO delete this line when date is on the balance node
    today = date.today()
    return datetime(today.year, today.month, today.day).isoformat()


def balances_with_adequate_values(sp, products, datestring=None):
    if datestring is None:
        datestring = long_date() + 'Z'

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
    return ("""
        <?xml version="1.0" encoding="UTF-8"?>
        <data uiVersion="1" version="33" name="New Form">
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
    """ % insides()).format(
        sp_id=sp._id,
        sp2_id=sp2._id,
        product0=products[0]._id,
        product1=products[1]._id,
        product2=products[2]._id,
        user_id=user._id,
        username=user.username,
        long_date=long_date() + 'Z',
    )


def balance_submission():
    return """
        <balance entity-id="{sp_id}" date="{long_date}">
            <product index="0" id="{product0}" quantity="35" />
            <product index="1" id="{product1}" quantity="46" />
            <product index="2" id="{product2}" quantity="25" />
        </balance>
    """


def transfer_dest_only():
    return """
        <receipts>
            <transfer dest="{sp_id}" date="{long_date}">
                <product index="0" id="{product0}" quantity="38" />
                <product index="1" id="{product1}" quantity="1" />
                <product index="2" id="{product2}" quantity="1" />
            </transfer>
        </receipts>
    """


def transfer_source_only():
    return """
        <losses>
            <transfer src="{sp_id}" date="{long_date}">
                <product index="0" id="{product0}" quantity="4" />
                <product index="1" id="{product1}" quantity="1" />
                <product index="2" id="{product2}" quantity="1" />
            </transfer>
        </losses>
    """


def transfer_both():
    # TODO Does this get wrapped in something? receipts?
    return """
        <transfer src="{sp_id}" dest="{sp2_id}" date="{long_date}">
            <product index="0" id="{product0}" quantity="4" />
            <product index="1" id="{product1}" quantity="1" />
            <product index="2" id="{product2}" quantity="1" />
        </transfer>
    """


def transfer_neither():
    return """
        <transfer date="{long_date}">
            <product index="0" id="{product0}" quantity="4" />
            <product index="1" id="{product1}" quantity="1" />
            <product index="2" id="{product2}" quantity="1" />
        </transfer>
    """


def balance_first():
    return balance_submission() + transfer_dest_only()


def transfer_first():
    return transfer_dest_only() + balance_submission()
