"""
NOTE: This module was added in September 2017 to provide utils for dealing
with immunization information in the AWW app, for the purpose of sending SMS
alerts related to immunizations. The immunization SMS alerts never ended up
being used, but I'm leaving these utils here in case it will be useful at
some later point. If you use these utils, you'll want to make sure the
AWW app still matches up with what is being done here in case there have
been changes since this was written, but this should at least
provide a base to start from. If a year goes by and no one uses this, it
can probably be removed along with the associated tests for it.

Each immunization is represented by a CommCare Supply product. When an
immunization is applied, it is recorded using a LedgerValue, where the entry_id
of the LedgerValue is the product's unique id, and the balance of the
LedgerValue is the date that the immunization took place, represented as an
integer (the number of days since 1970-01-01). The LedgerValues are tracked
against cases with case type "tasks".

Each immunization has a window within which it is valid to be applied, which
depends on a few factors, including whether it depends on another immunization
to happen first. All of this information is stored as custom product_data on the
CommCare Supply product.

These utils can be used to calculate when immunizations are due for a given
"tasks" case, whether that "tasks" case applies to a mother (case property
"tasks_type" == "pregnancy"), or a child (case property "tasks_type" == "child").
"""

from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.products.models import SQLProduct
from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL
from corehq.form_processor.models import CommCareCaseIndexSQL
from corehq.util.quickcache import quickcache
from custom.icds.case_relationships import (
    child_person_case_from_tasks_case,
    ccs_record_case_from_tasks_case,
)
from custom.icds.rules.util import get_date, todays_date
from datetime import datetime, date, timedelta
import six


def _validate_tasks_case_and_immunization_product(tasks_case, immunization_product):
    if tasks_case.get_case_property('tasks_type') != immunization_product.product_data.get('schedule'):
        raise ValueError("Mismatch between tasks.tasks_type and product.schedule")


def _validate_child_or_pregnancy_type(value):
    if value not in ('child', 'pregnancy'):
        raise ValueError("Expected one of: 'child', 'pregnancy'")


@quickcache(['domain', 'schedule'], timeout=60 * 60)
def get_immunization_products(domain, schedule):
    _validate_child_or_pregnancy_type(schedule)

    return [
        product
        for product in SQLProduct.active_objects.filter(domain=domain)
        if product.product_data.get('schedule', '').strip() == schedule
    ]


def get_tasks_case_immunization_ledger_values(tasks_case):
    if tasks_case.type != 'tasks':
        raise ValueError("Expected 'tasks' case")

    return LedgerAccessorSQL.get_ledger_values_for_cases([tasks_case.case_id], section_id='immuns')


def get_immunization_date(ledger_value):
    return date(1970, 1, 1) + timedelta(days=ledger_value.balance)


def get_immunization_anchor_date(tasks_case):
    tasks_type = tasks_case.get_case_property('tasks_type')
    _validate_child_or_pregnancy_type(tasks_type)

    if tasks_type == 'child':
        person = child_person_case_from_tasks_case(tasks_case)
        return get_date(person.get_case_property('dob'))
    elif tasks_type == 'pregnancy':
        ccs_record = ccs_record_case_from_tasks_case(tasks_case)
        return get_date(ccs_record.get_case_property('edd'))


def get_map(objects, attr):
    return {getattr(o, attr): o for o in objects}


def calculate_immunization_window(tasks_case, anchor_date, immunization_product, all_immunization_products,
        ledger_values):
    """
    :param tasks_case: the CommCareCaseSQL with case type 'tasks'
    :param anchor_date: the output from get_immunization_anchor_date
    :param immunization_product: the SQLProduct representing the immunization
    :param all_immunization_products: the output from get_immunization_products
    :param ledger_values: the output from get_tasks_case_immunization_ledger_values
    :return: (start date, end date) representing the window in which the immunization is valid
             start date can be None if the immunization's predecessor immunization did not take place
    """
    _validate_tasks_case_and_immunization_product(tasks_case, immunization_product)

    product_id_to_ledger_value = get_map(ledger_values, 'entry_id')
    product_code_to_product = get_map(all_immunization_products, 'code')

    valid = int(immunization_product.product_data.get('valid'))
    expires = int(immunization_product.product_data.get('expires'))
    eligible_start_date = anchor_date + timedelta(days=valid)
    end_date = anchor_date + timedelta(days=expires)

    predecessor_id = immunization_product.product_data.get('predecessor_id', '').strip()
    if predecessor_id:
        predecessor_product = product_code_to_product.get(predecessor_id)
        if predecessor_product is None:
            raise ValueError("Product %s not found" % predecessor_id)

        if predecessor_product.product_id not in product_id_to_ledger_value:
            start_date = None
        else:
            predecessor_ledger_value = product_id_to_ledger_value[predecessor_product.product_id]
            days_after_previous = int(immunization_product.product_data.get('days_after_previous'))
            start_date = max(
                eligible_start_date,
                get_immunization_date(predecessor_ledger_value) + timedelta(days=days_after_previous),
            )
    else:
        start_date = eligible_start_date

    return (start_date, end_date)


def immunization_is_due(tasks_case, anchor_date, immunization_product, all_immunization_products, ledger_values):
    """
    :param tasks_case: the CommCareCaseSQL with case type 'tasks'
    :param anchor_date: the output from get_immunization_anchor_date
    :param immunization_product: the SQLProduct representing the immunization
    :param all_immunization_products: the output from get_immunization_products
    :param ledger_values: the output from get_tasks_case_immunization_ledger_values
    :return: True if, based on the current date, the given immunization is due; False otherwise
    """
    _validate_tasks_case_and_immunization_product(tasks_case, immunization_product)

    # Check if the immunization has already happened
    product_id_to_ledger_value = get_map(ledger_values, 'entry_id')
    if immunization_product.product_id in product_id_to_ledger_value:
        return False

    # Check the product's schedule_flag vs the tasks_case schedule_flag, if applicable
    product_schedule_flag = immunization_product.product_data.get('schedule_flag', '').strip()
    if product_schedule_flag:
        tasks_case_schedule_flag = tasks_case.get_case_property('schedule_flag')
        if (
            not isinstance(tasks_case_schedule_flag, (six.text_type, bytes)) or
            product_schedule_flag not in tasks_case_schedule_flag
        ):
            return False

    # If all of the above checks pass, check that today's date falls within the immunization window
    today = todays_date(datetime.utcnow())

    start_date, end_date = calculate_immunization_window(
        tasks_case,
        anchor_date,
        immunization_product,
        all_immunization_products,
        ledger_values
    )

    return start_date is not None and today >= start_date and today <= end_date
