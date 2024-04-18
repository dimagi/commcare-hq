# Properties that are inconsistent between case models stored in HQ and casedb
# expressions. We store these as case properties in the case search index so
# they are easily searchable, then remove them when pulling the case source
# from ES

class _SystemProperty:
    key = None  # The user-facing property name
    is_datetime = False


class CaseID(_SystemProperty):
    key = '@case_id'
    value_getter = lambda doc: doc.get('_id')
    sort_property = '_id'


class CaseType(_SystemProperty):
    key = '@case_type'
    value_getter = lambda doc: doc.get('type')
    sort_property = 'type.exact'


class OwnerID(_SystemProperty):
    key = '@owner_id'
    value_getter = lambda doc: doc.get('owner_id')
    sort_property = 'owner_id'


class Status(_SystemProperty):
    key = '@status'
    value_getter = lambda doc: 'closed' if doc.get('closed') else 'open'
    sort_property = 'closed'


class Name(_SystemProperty):
    key = 'name'
    value_getter = lambda doc: doc.get('name')
    sort_property = 'name.exact'


class CaseName(_SystemProperty):
    key = 'case_name'
    value_getter = lambda doc: doc.get('name')
    sort_property = 'name.exact'


class ExternalID(_SystemProperty):
    key = 'external_id'
    value_getter = lambda doc: doc.get('external_id', '')
    sort_property = 'external_id'


class DateOpened(_SystemProperty):
    key = 'date_opened'
    value_getter = lambda doc: doc.get('opened_on')
    sort_property = 'opened_on'
    is_datetime = True


class ClosedOn(_SystemProperty):
    key = 'closed_on'
    value_getter = lambda doc: doc.get('closed_on')
    sort_property = 'closed_on'
    is_datetime = True


class LastModified(_SystemProperty):
    key = 'last_modified'
    value_getter = lambda doc: doc.get('modified_on')
    sort_property = 'modified_on'
    is_datetime = True


SPECIAL_CASE_PROPERTIES_MAP = {prop.key: prop for prop in _SystemProperty.__subclasses__()}
