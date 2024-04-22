"""
System properties are top level, schema'd properties on CommCareCase that are
made available to the user in interactions with the case search elasticsearch
index.

These are stored along with dynamic case properties in the case search index to
be easily searchable, then removed when pulling the case source from ES.
"""


class _SystemProperty:
    key = None  # The user-facing property name
    system_name = None  # The CommCareCase field name
    _es_field_name = None  # Path to use for ES logic, if not system_name
    is_datetime = False

    @classmethod
    def get_value(cls, doc):
        return doc.get(cls.system_name)

    @classmethod
    @property
    def es_field_name(cls):
        return cls._es_field_name or cls.system_name


class CaseID(_SystemProperty):
    key = '@case_id'
    system_name = '_id'


class CaseType(_SystemProperty):
    key = '@case_type'
    system_name = 'type'
    _es_field_name = 'type.exact'


class OwnerID(_SystemProperty):
    key = '@owner_id'
    system_name = 'owner_id'


class Status(_SystemProperty):
    key = '@status'
    system_name = 'closed'

    @classmethod
    def get_value(cls, doc):
        return 'closed' if doc.get('closed') else 'open'


class Name(_SystemProperty):
    key = 'name'
    system_name = 'name'
    _es_field_name = 'name.exact'


class CaseName(_SystemProperty):
    key = 'case_name'
    system_name = 'name'
    sort_property = 'name.exact'


class ExternalID(_SystemProperty):
    key = 'external_id'
    system_name = 'external_id'

    @classmethod
    def get_value(cls, doc):
        return doc.get('external_id', '')


class DateOpened(_SystemProperty):
    key = 'date_opened'
    system_name = 'opened_on'
    is_datetime = True


class ClosedOn(_SystemProperty):
    key = 'closed_on'
    system_name = 'closed_on'
    is_datetime = True


class LastModified(_SystemProperty):
    key = 'last_modified'
    system_name = 'modified_on'
    is_datetime = True


SPECIAL_CASE_PROPERTIES_MAP = {prop.key: prop for prop in _SystemProperty.__subclasses__()}
