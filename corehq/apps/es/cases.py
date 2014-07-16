from .es_query import HQESQuery


class CaseES(HQESQuery):
    index = 'cases'
    default_filters = {
        'is_commcare_case': {"term": {"doc_type": "CommCareCase"}},
    }
