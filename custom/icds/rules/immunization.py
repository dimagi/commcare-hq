import pytz
import re
from corehq.apps.products.models import SQLProduct
from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL
from corehq.form_processor.models import CommCareCaseIndexSQL
from corehq.util.quickcache import quickcache
from corehq.util.timezones.conversions import ServerTime
from datetime import datetime, date, timedelta


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


def get_and_check_parent_case(subcase, identifier, relationship, expected_case_type):
    related = subcase.get_parent(identifier=identifier, relationship=relationship)
    if len(related) != 1:
        raise ValueError("Expected exactly 1 matching case, found %s" % len(related))

    parent_case = related[0]
    if parent_case.type != expected_case_type:
        raise ValueError("Expected case type %s, found %s" % (expected_case_type, parent_case.type))

    return parent_case


def child_person_case_from_tasks_case(tasks_case):
    child_health_case = get_and_check_parent_case(
        tasks_case,
        'parent',
        CommCareCaseIndexSQL.EXTENSION,
        'child_health'
    )

    return get_and_check_parent_case(
        child_health_case,
        'parent',
        CommCareCaseIndexSQL.EXTENSION,
        'person'
    )


def ccs_record_case_from_tasks_case(tasks_case):
    return get_and_check_parent_case(
        tasks_case,
        'parent',
        CommCareCaseIndexSQL.EXTENSION,
        'ccs_record'
    )


def get_date(value):
    if isinstance(value, date):
        if isinstance(value, datetime):
            return value.date()

        return value

    if not isinstance(value, basestring):
        raise TypeError("Expected date, datetime, or string")

    if not re.match('^\d{4}-\d{2}-\d{2}', value):
        raise ValueError("Expected a date string")

    return datetime.strptime(value, '%Y-%m-%d').date()


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
    product_id_to_product = get_map(all_immunization_products, 'product_id')

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


def todays_date():
    return ServerTime(datetime.utcnow()).user_time(pytz.timezone('Asia/Kolkata')).done().date()


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
            not isinstance(tasks_case_schedule_flag, basestring) or
            product_schedule_flag not in tasks_case_schedule_flag
        ):
            return False

    # If all of the above checks pass, check that today's date falls within the immunization window
    today = todays_date()

    start_date, end_date = calculate_immunization_window(
        tasks_case,
        anchor_date,
        immunization_product,
        all_immunization_products,
        ledger_values
    )

    return start_date is not None and today >= start_date and today <= end_date
