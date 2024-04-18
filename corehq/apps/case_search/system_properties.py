from collections import namedtuple


def get_field_lambda(field_name):
    return lambda model: model._meta.get_field(field_name)


# Properties that are inconsistent between case models stored in HQ and casedb
# expressions. We store these as case properties in the case search index so
# they are easily searchable, then remove them when pulling the case source
# from ES
SpecialCaseProperty = namedtuple('SpecialCaseProperty', 'key value_getter sort_property field_getter')
SPECIAL_CASE_PROPERTIES_MAP = {
    '@case_id': SpecialCaseProperty(
        '@case_id',
        lambda doc: doc.get('_id'),
        '_id',
        get_field_lambda('case_id'),
    ),
    '@case_type': SpecialCaseProperty(
        '@case_type',
        lambda doc: doc.get('type'),
        'type.exact',
        get_field_lambda('type'),
    ),
    '@owner_id': SpecialCaseProperty(
        '@owner_id',
        lambda doc: doc.get('owner_id'),
        'owner_id',
        get_field_lambda('owner_id'),
    ),
    '@status': SpecialCaseProperty(
        '@status',
        lambda doc: 'closed' if doc.get('closed') else 'open',
        'closed',
        get_field_lambda('closed'),
    ),
    'name': SpecialCaseProperty(
        'name',
        lambda doc: doc.get('name'),
        'name.exact',
        get_field_lambda('name'),
    ),
    'case_name': SpecialCaseProperty(
        'case_name',
        lambda doc: doc.get('name'),
        'name.exact',
        get_field_lambda('name'),
    ),
    'external_id': SpecialCaseProperty(
        'external_id',
        lambda doc: doc.get('external_id', ''),
        'external_id',
        get_field_lambda('external_id'),
    ),
    'date_opened': SpecialCaseProperty(
        'date_opened',
        lambda doc: doc.get('opened_on'),
        'opened_on',
        get_field_lambda('opened_on'),
    ),
    'closed_on': SpecialCaseProperty(
        'closed_on',
        lambda doc: doc.get('closed_on'),
        'closed_on',
        get_field_lambda('closed_on'),
    ),
    'last_modified': SpecialCaseProperty(
        'last_modified',
        lambda doc: doc.get('modified_on'),
        'modified_on',
        get_field_lambda('modified_on'),
    ),
}