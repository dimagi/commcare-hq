from .es_query import HQESQuery


class CaseES(HQESQuery):
    index = 'cases'
