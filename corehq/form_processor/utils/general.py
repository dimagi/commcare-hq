def use_sqlite_backend(domain_name):
    return True


def is_commcarecase(obj):
    from corehq.form_processor.models import CommCareCase
    return isinstance(obj, CommCareCase)
