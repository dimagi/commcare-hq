from __future__ import absolute_import
from __future__ import unicode_literals
from dimagi.utils.parsing import json_format_datetime
from dimagi.utils.couch.undo import DELETED_SUFFIX

from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL


def get_group_ids_by_last_modified(start_datetime, end_datetime):
    '''
    Returns all group ids that have been modified within a time range. The start date is
    exclusive while the end date is inclusive (start_datetime, end_datetime].
    '''
    from corehq.apps.groups.models import Group
    doc_types = [
        'Group',
        'Group{}'.format(DELETED_SUFFIX),
    ]
    return _get_ids_by_last_modified(Group, doc_types, start_datetime, end_datetime)


def get_user_ids_by_last_modified(start_datetime, end_datetime):
    '''
    Returns all user ids that have been modified within a time range. The start date is
    exclusive while the end date is inclusive (start_datetime, end_datetime].
    '''
    from corehq.apps.users.models import CouchUser
    doc_types = [
        'CouchUser',
        'CouchUser{}'.format(DELETED_SUFFIX),
    ]
    return _get_ids_by_last_modified(CouchUser, doc_types, start_datetime, end_datetime)


def get_domain_ids_by_last_modified(start_datetime, end_datetime):
    '''
    Returns all domain ids that have been modified within a time range. The start date is
    exclusive while the end date is inclusive (start_datetime, end_datetime].
    '''
    from corehq.apps.domain.models import Domain
    doc_types = [
        'Domain',
        'Domain{}'.format(DELETED_SUFFIX),
    ]
    return _get_ids_by_last_modified(Domain, doc_types, start_datetime, end_datetime)


def _get_ids_by_last_modified(cls, doc_types, start_datetime, end_datetime):
    json_start_datetime = json_format_datetime(start_datetime)
    for doc_type in doc_types:
        results = cls.view(
            'last_modified/by_last_modified',
            startkey=[doc_type, json_start_datetime],
            endkey=[doc_type, json_format_datetime(end_datetime)],
            include_docs=False,
            reduce=False,
        )
        for result in results:
            result_modified_datetime = result['key'][1]
            # Skip the record if the datetime is equal to the start because this should return
            # records with an exclusive start date.
            if result_modified_datetime == json_start_datetime:
                continue
            yield result['id']


def get_synclogs_by_date(start_datetime, end_datetime):
    '''
    Returns all synclogs that have been modified within a time range. The start date is
    exclusive while the end date is inclusive (start_datetime, end_datetime].
    '''
    from casexml.apps.phone.models import SyncLogSQL

    return SyncLogSQL.objects.filter(date__gt=start_datetime, date__lte=end_datetime).defer('doc').iterator()


def get_forms_by_last_modified(start_datetime, end_datetime):
    '''
    Returns all form ids that have been modified within a time range. The start date is
    exclusive while the end date is inclusive (start_datetime, end_datetime].
    '''
    return FormAccessorSQL.iter_forms_by_last_modified(start_datetime, end_datetime)

    # TODO Couch forms


def get_application_ids_by_last_modified(start_datetime, end_datetime):
    '''
    Returns all application ids that have been modified within a time range. The start date is
    exclusive while the end date is inclusive (start_datetime, end_datetime].
    '''
    from corehq.apps.app_manager.models import Application
    doc_types = [
        'ApplicationBase',
        'ApplicationBase{}'.format(DELETED_SUFFIX),
    ]
    return _get_ids_by_last_modified(Application, doc_types, start_datetime, end_datetime)
