import sys
from collections import defaultdict
from datetime import datetime, timedelta

from django.conf import settings
from django.core.management import color_style
from django.utils.functional import cached_property
from field_audit.models import AuditAction

from dimagi.utils.couch.database import iter_bulk_delete

from corehq.apps.cleanup.models import DeletedCouchDoc
from corehq.apps.domain.models import Domain
from corehq.util.couch import get_db_by_doc_type


def abort():
    print("Aborting")
    sys.exit(1)


def confirm_destructive_operation():
    style = color_style()
    print(style.ERROR("\nHEY! This is wicked dangerous, pay attention."))
    print(style.WARNING("\nThis operation irreversibly deletes a lot of stuff."))
    print(f"\nSERVER_ENVIRONMENT = {settings.SERVER_ENVIRONMENT}")

    if settings.IS_SAAS_ENVIRONMENT:
        print("This command isn't meant to be run on a SAAS environment")
        abort()

    confirm("Are you SURE you want to proceed?")


def confirm(msg):
    print(msg)
    if input("(y/N)") != 'y':
        abort()


class DeletedDomains:
    """
    The logic to ensure a domain is deleted is inefficient.
    This object takes advantage of the fact that we typically want this info
    on more than one domain, so it makes sense to cache the results of deleted
    and active domains.
    """

    @cached_property
    def _deleted_domains(self):
        return Domain.get_deleted_domain_names()

    def is_domain_deleted(self, domain):
        return domain in self._deleted_domains


def migrate_to_deleted_on(db_cls, old_field, should_audit=False):
    """
    Fetches all objects from a specified SQL table that have been soft deleted
    and sets "deleted_on" to the current time
    :param db_cls: class of the SQL table to migrate (e.g. AutomaticUpdateRule)
    :param old_field: str of the previous field (e.g. "deleted" or "is_deleted")
    :param should_audit: set to True if audit_action needs to be specified on
    Queryset method
    NOTE: can remove this once the deleted_on migration is complete
    """
    filter_kwargs = {old_field: True}
    queryset = db_cls.objects.filter(**filter_kwargs)

    update_kwargs = {'deleted_on': datetime.utcnow()}
    if should_audit:
        update_kwargs['audit_action'] = AuditAction.AUDIT
    update_count = queryset.update(**update_kwargs)
    return update_count


def hard_delete_couch_docs_before_cutoff(cutoff):
    """
    Permanently deletes couch objects with deleted_on set to a datetime earlier
    than the specified cutoff datetime
    :param cutoff: datetime used to obtain couch docs to be hard deleted
    :return: dictionary of count of deleted objects per table
    """
    counts = {}
    deleted_docs = DeletedCouchDoc.objects.filter(deleted_on__lt=cutoff)

    doc_ids_by_doc_type = defaultdict(list)
    for doc in deleted_docs:
        doc_ids_by_doc_type[doc.doc_type].append(doc.doc_id)

    for doc_type in doc_ids_by_doc_type.keys():
        db = get_db_by_doc_type(doc_type)
        doc_ids = doc_ids_by_doc_type[doc_type]
        counts[doc_type] = len(doc_ids)
        iter_bulk_delete(db, doc_ids)
        sql_objs = DeletedCouchDoc.objects.filter(doc_type=doc_type, doc_id__in=doc_ids)
        sql_objs.delete()

    return counts


def get_cutoff_date_for_data_deletion():
    return datetime.utcnow() - timedelta(days=settings.PERMANENT_DELETION_WINDOW)

