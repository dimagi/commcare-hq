

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


def get_form_export_instances(domain):
    from .models import FormExportInstance

    key = [domain, 'FormExportInstance']
    return _get_export_instance(FormExportInstance, key)


def get_case_export_instances(domain):
    from .models import CaseExportInstance

    key = [domain, 'CaseExportInstance']
    return _get_export_instance(CaseExportInstance, key)


def _get_export_instance(cls, key):
    results = cls.get_db().view(
        'export_instances_by_domain/view',
        startkey=key,
        endkey=key + [{}],
        include_docs=True,
        reduce=False,
    ).all()
    return [cls.wrap(result['doc']) for result in results]


def get_all_daily_saved_export_instances():
    from .models import ExportInstance
    results = ExportInstance.get_db().view(
        "export_instances_by_is_daily_saved/view",
        startkey=[True],
        endkey=[True, {}],
        include_docs=True,
        reduce=False,
    ).all()
    return [_properly_wrap_export_instance(result['doc']) for result in results]


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
