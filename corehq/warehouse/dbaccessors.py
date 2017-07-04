from dimagi.utils.parsing import json_format_datetime
from dimagi.utils.couch.undo import DELETED_SUFFIX


def get_group_ids_by_last_modified(start_datetime, end_datetime):
    from corehq.apps.groups.models import Group
    doc_types = [
        'Group',
        'Group{}'.format(DELETED_SUFFIX),
    ]
    return _get_ids_by_last_modified(Group, doc_types, start_datetime, end_datetime)


def get_user_ids_by_last_modified(start_datetime, end_datetime):
    from corehq.apps.users.models import CouchUser
    doc_types = [
        'CouchUser',
        'CouchUser{}'.format(DELETED_SUFFIX),
    ]
    return _get_ids_by_last_modified(CouchUser, doc_types, start_datetime, end_datetime)


def get_domain_ids_by_last_modified(start_datetime, end_datetime):
    from corehq.apps.domain.models import Domain
    doc_types = [
        'Domain',
        'Domain{}'.format(DELETED_SUFFIX),
    ]
    return _get_ids_by_last_modified(Domain, doc_types, start_datetime, end_datetime)


def _get_ids_by_last_modified(cls, doc_types, start_datetime, end_datetime):
    for doc_type in doc_types:
        results = cls.view(
            'last_modified/by_last_modified',
            startkey=[doc_type, json_format_datetime(start_datetime)],
            endkey=[doc_type, json_format_datetime(end_datetime)],
            include_docs=False,
            reduce=False,
        )
        for result in results:
            yield result['id']
