


def send_xforms(domain, start_date, end_date):
    # ...
    for xform in form_accessors.iter_forms_by_last_modified(start_date, end_date):
        create_repeat_records(dhis2_repeater, xform)
