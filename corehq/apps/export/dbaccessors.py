from __future__ import absolute_import
from __future__ import unicode_literals
from dimagi.utils.couch.database import safe_delete
from corehq.util.test_utils import unit_testing_only
from dimagi.utils.parsing import json_format_datetime


def get_latest_case_export_schema(domain, case_type):
    from .models import CaseExportDataSchema

    key = [domain, 'CaseExportDataSchema', case_type]
    return _get_latest_export_schema(CaseExportDataSchema, key)


def get_latest_form_export_schema(domain, app_id, xmlns):
    from .models import FormExportDataSchema

    key = [domain, 'FormExportDataSchema', app_id, xmlns]
    return _get_latest_export_schema(FormExportDataSchema, key)


def _get_latest_export_schema(cls, key):
    result = cls.get_db().view(
        'schemas_by_xmlns_or_case_type/view',
        startkey=key + [{}],
        endkey=key,
        include_docs=True,
        limit=1,
        reduce=False,
        descending=True,
    ).first()
    return cls.wrap(result['doc']) if result else None


def get_case_inferred_schema(domain, case_type):
    from .models import CaseInferredSchema

    key = [domain, 'CaseInferredSchema', case_type]
    result = CaseInferredSchema.get_db().view(
        'schemas_by_xmlns_or_case_type/view',
        startkey=key + [{}],
        endkey=key,
        include_docs=True,
        limit=1,
        reduce=False,
        descending=True,
    ).first()
    return CaseInferredSchema.wrap(result['doc']) if result else None


def get_form_inferred_schema(domain, app_id, xmlns):
    from .models import FormInferredSchema

    key = [domain, 'FormInferredSchema', app_id, xmlns]
    result = FormInferredSchema.get_db().view(
        'schemas_by_xmlns_or_case_type/view',
        startkey=key + [{}],
        endkey=key,
        include_docs=True,
        limit=1,
        reduce=False,
        descending=True,
    ).first()
    return FormInferredSchema.wrap(result['doc']) if result else None


def get_form_export_instances(domain):
    from .models import FormExportInstance

    key = [domain, 'FormExportInstance']
    return _get_export_instance(FormExportInstance, key)


def get_case_export_instances(domain):
    from .models import CaseExportInstance

    key = [domain, 'CaseExportInstance']
    return _get_export_instance(CaseExportInstance, key)


def _get_saved_exports(domain, has_deid_permissions, new_exports_getter):
    exports = new_exports_getter(domain)
    if not has_deid_permissions:
        exports = [e for e in exports if not e.is_safe]
    return sorted(exports, key=lambda x: x.name)


def get_case_exports_by_domain(domain, has_deid_permissions):
    return _get_saved_exports(domain, has_deid_permissions, get_case_export_instances)


def get_form_exports_by_domain(domain, has_deid_permissions):
    return _get_saved_exports(domain, has_deid_permissions, get_form_export_instances)


def get_export_count_by_domain(domain):
    from .models import ExportInstance

    export_result = ExportInstance.get_db().view(
        'export_instances_by_domain/view',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=False,
        reduce=True,
    ).one()
    return 0 if export_result is None else export_result['value']


def get_deid_export_count(domain):
    from .models import ExportInstance
    return sum(res['value'] for res in ExportInstance.get_db().view(
        'export_instances_by_domain/view',
        keys=[[domain, 'FormExportInstance', True],
              [domain, 'CaseExportInstance', True]],
        include_docs=False,
        group=True,
    ).all())


def _get_export_instance(cls, key):
    results = cls.get_db().view(
        'export_instances_by_domain/view',
        startkey=key,
        endkey=key + [{}],
        include_docs=True,
        reduce=False,
    ).all()
    return [cls.wrap(result['doc']) for result in results]


def get_daily_saved_export_ids_for_auto_rebuild(accessed_after):
    """
    get all saved exports accessed after the timestamp
    :param accessed_after: datetime to get reports that have been accessed after this timestamp
    """
    from .models import ExportInstance
    # get exports that have not been accessed yet
    new_exports = ExportInstance.get_db().view(
        "export_instances_by_is_daily_saved/view",
        include_docs=False,
        key=[None],
        reduce=False,
    ).all()
    export_ids = [export['id'] for export in new_exports]

    # get exports that have last_accessed set after the cutoff requested
    accessed_reports = ExportInstance.get_db().view(
        "export_instances_by_is_daily_saved/view",
        include_docs=False,
        startkey=[json_format_datetime(accessed_after)],
        reduce=False,
    ).all()
    export_ids.extend([result['id'] for result in accessed_reports])
    return export_ids


def get_properly_wrapped_export_instance(doc_id):
    from .models import ExportInstance
    doc = ExportInstance.get_db().get(doc_id)
    return _properly_wrap_export_instance(doc)


def _properly_wrap_export_instance(doc):
    from .models import FormExportInstance
    from .models import CaseExportInstance
    from .models import ExportInstance
    class_ = {
        "FormExportInstance": FormExportInstance,
        "CaseExportInstance": CaseExportInstance,
    }.get(doc['doc_type'], ExportInstance)
    return class_.wrap(doc)


@unit_testing_only
def delete_all_export_data_schemas():
    from .models import ExportDataSchema

    db = ExportDataSchema.get_db()
    for row in db.view('schemas_by_xmlns_or_case_type/view', reduce=False):
        doc_id = row['id']
        safe_delete(db, doc_id)


@unit_testing_only
def delete_all_export_instances():
    from .models import ExportInstance

    db = ExportInstance.get_db()
    for row in db.view('export_instances_by_domain/view', reduce=False):
        doc_id = row['id']
        safe_delete(db, doc_id)
