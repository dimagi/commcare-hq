from custom.icds.case_relationships import (
    child_person_case_from_child_health_case,
    mother_person_case_from_ccs_record_case,
    child_person_case_from_tasks_case,
    mother_person_case_from_tasks_case,
)
from custom.icds.rules.immunization import (
    get_immunization_products,
    get_immunization_anchor_date,
    get_map,
    calculate_immunization_window,
    get_tasks_case_immunization_ledger_values,
    todays_date
)


def consider_case_for_dpt3_and_measles_reminder(case, now):
    """
    The purpose of this function is to determine if we should consider the
    given case for the later check that happens when we check if DPT3 and
    Measles vaccinations are due.

    The actual check for whether the immunizations are due happens at reminder
    runtime. The purpose of this function which is referenced in the rule
    is to just filter down that list of cases under consideration so that
    we process as few as necessary.
    """
    if case.type != 'tasks':
        raise ValueError("This rule criteria should only be applied to cases with case type 'tasks'")

    if case.get_case_property('tasks_type') != 'child':
        return False

    products = get_immunization_products(case.domain, 'child')
    product_code_to_product = get_map(products, 'code')
    dpt3_product = product_code_to_product['3g_dpt_3']
    measles_product = product_code_to_product['4g_measles']

    ledger_values = get_tasks_case_immunization_ledger_values(case)
    product_id_to_ledger_value = get_map(ledger_values, 'entry_id')

    # If either of the vaccinations have happened, do not consider the case
    if (
        dpt3_product.product_id in product_id_to_ledger_value or
        measles_product.product_id in product_id_to_ledger_value
    ):
        return False

    today = todays_date()
    anchor_date = get_immunization_anchor_date(case)

    _, dpt3_end_date = calculate_immunization_window(
        case,
        anchor_date,
        dpt3_product,
        products,
        ledger_values
    )

    _, measles_end_date = calculate_immunization_window(
        case,
        anchor_date,
        measles_product,
        products,
        ledger_values
    )

    # If either of the vaccination windows have expired, do not consider the case
    if today > dpt3_end_date or today > measles_end_date:
        return False

    return True


def person_case_is_not_migrated(case, now):
    if case.type != 'person':
        raise ValueError("Expected case type of 'person' for %s" % case.case_id)

    return not (
        case.get_case_property('migration_status') == 'migrated' or
        case.get_case_property('registered_status') == 'not_registered'
    )


def child_health_case_is_not_migrated(case, now):
    child_person_case = child_person_case_from_child_health_case(case)
    return person_case_is_not_migrated(child_person_case, now)


def ccs_record_case_is_not_migrated(case, now):
    mother_person_case = mother_person_case_from_ccs_record_case(case)
    return person_case_is_not_migrated(mother_person_case, now)


def tasks_case_is_not_migrated(case, now):
    tasks_type = case.get_case_property('tasks_type')
    if tasks_type == 'child':
        child_person_case = child_person_case_from_tasks_case(case)
        return person_case_is_not_migrated(child_person_case, now)
    elif tasks_type == 'pregnancy':
        mother_person_case = mother_person_case_from_tasks_case(case)
        return person_case_is_not_migrated(mother_person_case, now)
    else:
        raise ValueError("Expected tasks_type of 'child' or 'pregnancy' for %s" % case.case_id)
