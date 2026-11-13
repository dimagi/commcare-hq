"""Find and repair cases with transactions for deleted forms.

Archiving a form revokes its case transactions. Deleting a form without
first archiving it leaves non-revoked transactions behind:

- A soft deleted form keeps its state, so rebuilding the case still
  applies its updates.
- Once the form is hard deleted, which happens automatically to soft
  deleted forms, rebuilding the case raises ``XFormNotFound``. That
  blocks anything that rebuilds the case, such as archiving, unarchiving
  or editing its other forms.

Repairing a case revokes those transactions, as archiving the forms
would have, and rebuilds the case without them.
"""

from dataclasses import dataclass, field, replace

from django.db.models import F

from corehq.form_processor.backends.sql.dbaccessors import CaseReindexAccessor
from corehq.form_processor.models import (
    CaseTransaction,
    XFormInstance,
)
from corehq.sql_db.util import split_list_by_db_partition


@dataclass(frozen=True)
class ScanPosition:
    """Where a scan of a domain's cases got to, for resuming it"""

    done_db_aliases: tuple = ()
    db_alias: str | None = None
    last_pk: int | None = None


@dataclass(frozen=True)
class ScanPage:
    """Results for one page of scanned cases"""

    position: ScanPosition
    case_count: int
    deleted_form_ids_by_case: dict = field(default_factory=dict)


def iter_scan_pages(
    domain, position=None, include_deleted=False, page_size=1000
):
    """Scan cases in ``domain`` for transactions whose form is deleted.

    Yields a ``ScanPage`` per page of cases. Pass the ``position`` of the
    last page processed to resume a scan.
    """
    position = position or ScanPosition()
    accessor = CaseReindexAccessor(
        domain=domain, include_deleted=include_deleted
    )
    for db_alias in accessor.sql_db_aliases:
        if db_alias in position.done_db_aliases:
            continue
        last_pk = position.last_pk if position.db_alias == db_alias else None
        while rows := list(
            accessor.get_doc_ids(
                db_alias, last_doc_pk=last_pk, limit=page_size
            )
        ):
            last_pk = rows[-1].primary_key
            position = replace(position, db_alias=db_alias, last_pk=last_pk)
            yield ScanPage(
                position=position,
                case_count=len(rows),
                deleted_form_ids_by_case=find_deleted_form_ids(
                    db_alias, [r.doc_id for r in rows]
                ),
            )
        position = ScanPosition(
            done_db_aliases=position.done_db_aliases + (db_alias,)
        )


def find_deleted_form_ids(db_alias, case_ids):
    """Return ``{case_id: deleted_form_ids}`` for cases on ``db_alias``
    with non-revoked form transactions whose form is soft or hard deleted.

    Case transactions live on the same shard as their case.
    """
    form_ids_by_case = {}
    for case_id, form_id in (
        CaseTransaction.objects.using(db_alias)
        .annotate(type_filter=F('type').bitand(CaseTransaction.TYPE_FORM))
        .filter(
            case_id__in=case_ids,
            revoked=False,
            type_filter=CaseTransaction.TYPE_FORM,
            form_id__isnull=False,
        )
        .values_list('case_id', 'form_id')
    ):
        form_ids_by_case.setdefault(case_id, set()).add(form_id)

    all_form_ids = set().union(*form_ids_by_case.values())
    deleted = all_form_ids - get_undeleted_form_ids(all_form_ids)
    return {
        case_id: form_ids & deleted
        for case_id, form_ids in form_ids_by_case.items()
        if form_ids & deleted
    }


def get_undeleted_form_ids(form_ids):
    """Return the ids in ``form_ids`` of forms that exist and are not soft
    deleted
    """
    undeleted = set()
    for db_alias, ids in split_list_by_db_partition(form_ids):
        undeleted.update(
            XFormInstance.objects.using(db_alias)
            .filter(form_id__in=ids, deleted_on__isnull=True)
            .values_list('form_id', flat=True)
        )
    return undeleted
