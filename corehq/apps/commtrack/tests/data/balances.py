from datetime import date, datetime


def long_date():
    return ''
    today = date.today()
    return datetime(today.year, today.month, today.day).isoformat()


def blank_balances(sp, products):
    return """
        <ns0:balance xmlns:ns0="http://commtrack.org/stock_report" xmlns="http://openrosa.org/http/response" date="{long_date}" entity-id="{sp_id}">
            <ns0:product consumption_rate="10.0" id="{product0}" quantity="" stock_category="nodata" stockout_since=""/>
            <ns0:product consumption_rate="10.0" id="{product1}" quantity="" stock_category="nodata" stockout_since=""/>
            <ns0:product consumption_rate="10.0" id="{product2}" quantity="" stock_category="nodata" stockout_since=""/>
        </ns0:balance>
    """.format(
        sp_id=sp._id,
        long_date=long_date() + 'Z',
        product0=products[0]._id,
        product1=products[1]._id,
        product2=products[2]._id,
    )
