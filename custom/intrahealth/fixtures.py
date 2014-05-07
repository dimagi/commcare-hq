from calendar import month_name
from xml.etree import ElementTree
from datetime import datetime
from custom.intrahealth import INTRAHEALTH_DOMAINS
from custom.intrahealth.models import PaymentTracking
from dimagi.utils.dates import add_months
from django.utils.translation import ugettext as _


def month_fixture(user, version, last_sync):
    """
    Very simple fixture generator that just returns recent months:

    Intentionally designed to look like an item list.

    <fixture id="intrahealth:months" user_id="217ce8d8e4cb726ca11c418dd00280d2">
        <month_list>
            <month>
                <id>5-2014</id>
                <name>May</name>
            </month>
            <month>
                <id>4-2014</id>
                <name>April</name>
            </month>
            <month>
                <id>3-2014</id>
                <name>March</name>
            </month>
            <month>
                <id>2-2014</id>
                <name>February</name>
            </month>
            <month>
                <id>1-2014</id>
                <name>January</name>
            </month>
            <month>
                <id>12-2013</id>
                <name>December</name>
            </month>
        </month_list>
    </fixture>
    """
    if user.domain in INTRAHEALTH_DOMAINS:
        root = ElementTree.Element('fixture',
                                   attrib={'id': 'intrahealth:months',
                                           'user_id': user.user_id})
        month_list = ElementTree.Element('month_list')
        root.append(month_list)
        for year, month in _recent_months(6):
            month_el = ElementTree.Element('month')
            month_el.append(_month_id_el(year, month))
            name_el = ElementTree.Element('name')
            name_el.text = _(month_name[month])
            month_el.append(name_el)
            month_list.append(month_el)
        return [root]


def payment_fixture(user, version, last_sync):
    if user.domain in INTRAHEALTH_DOMAINS:
        root = ElementTree.Element('fixture',
                                   attrib={'id': 'intrahealth:payments',
                                           'user_id': user.user_id})

        payment_list = ElementTree.Element('payment_list')
        root.append(payment_list)
        for year, month in _recent_months(6):
            # todo: need to figure out how the structure should look for cases within a period
            # semi-working code below
            for payment in PaymentTracking.objects.filter(year=year, month=month):  # todo: should filter by user info somehow tbd
                payment_el = ElementTree.Element('payment')
                payment_el.append(_month_id_el(year, month))
                for field in ('case_id', 'calculated_amount_owed', 'actual_amount_owed', 'amount_paid'):
                    field_el = ElementTree.Element(field)
                    field_el.text = getattr(payment, field) or '0'
                    payment_el.append(field_el)

        return [root]


def _recent_months(count):
    current_date = datetime.utcnow()
    for i in range(count):
        yield add_months(current_date.year, current_date.month, -i)


def _month_id_el(year, month):
    id_el = ElementTree.Element('id')
    id_el.text = '{month}-{year}'.format(month=month, year=year)
    return id_el
