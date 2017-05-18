from dimagi.utils.parsing import json_format_datetime


def get_group_ids_by_last_modified(start_datetime, end_datetime):
    from corehq.apps.groups.models import Group
    return _get_ids_by_last_modified(Group, start_datetime, end_datetime)


def get_domain_ids_by_last_modified(start_datetime, end_datetime):
    from corehq.apps.domain.models import Domain
    return _get_ids_by_last_modified(Domain, start_datetime, end_datetime)


def _get_ids_by_last_modified(cls, start_datetime, end_datetime):
    return [result['id'] for result in cls.view(
        'last_modified/by_last_modified',
        startkey=json_format_datetime(start_datetime),
        endkey=json_format_datetime(end_datetime),
        include_docs=False,
        reduce=False,
    ).all()]
