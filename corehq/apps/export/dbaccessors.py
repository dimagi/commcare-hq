

def get_latest_case_export_schema(domain, case_type):
    from .models import CaseExportDataSchema

    key = [domain, 'CaseExportDataSchema', case_type]
    result = CaseExportDataSchema.get_db().view(
        'schemas_by_xmlns_or_case_type/view',
        startkey=key + [{}],
        endkey=key,
        include_docs=True,
        limit=1,
        reduce=False,
        descending=True,
    ).first()
    return CaseExportDataSchema.wrap(result['doc']) if result else None


def get_latest_form_export_schema(domain, app_id, xmlns):
    from .models import FormExportDataSchema

    key = [domain, 'FormExportDataSchema', app_id, xmlns]
    result = FormExportDataSchema.get_db().view(
        'schemas_by_xmlns_or_case_type/view',
        startkey=key + [{}],
        endkey=key,
        include_docs=True,
        limit=1,
        reduce=False,
        descending=True,
    ).first()
    return FormExportDataSchema.wrap(result['doc']) if result else None
