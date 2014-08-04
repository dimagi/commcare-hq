from .es_query import HQESQuery


class DomainES(HQESQuery):
    index = 'domains'
