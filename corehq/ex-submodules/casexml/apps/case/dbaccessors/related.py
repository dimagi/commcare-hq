from casexml.apps.case.sharedmodels import CommCareCaseIndex


def get_reverse_indices_json(domain, case_id):
    from casexml.apps.case.models import CommCareCase
    return CommCareCase.get_db().view(
        "case_indices/related",
        startkey=[domain, case_id, "reverse_index"],
        endkey=[domain, case_id, "reverse_index", {}],
        reduce=False,
        wrapper=lambda r: r['value'],
    ).all()


def get_reverse_indices(case):
    return get_reverse_indices_for_case_id(case['domain'], case['_id'])


def get_reverse_indices_for_case_id(domain, case_id):
    return [CommCareCaseIndex.wrap(raw)
            for raw in get_reverse_indices_json(domain, case_id)]
