

def get_latest_case_export_schema_id(domain, case_type):
    from .models import ExportDataSchema

    key = [domain, 'CaseExportDataSchema', case_type]
    result = ExportDataSchema.get_db().view(
        'schemas_by_xmlns_or_case_type/view',
        startkey=key,
        endkey=key + [{}],
        include_docs=False,
        limit=1,
    ).first()
    return result['id'] if result else None


def get_latest_form_export_schema_id(domain, app_id, xmlns):
    from .models import ExportDataSchema

    key = [domain, 'FormExportDataSchema', app_id, xmlns]
    result = ExportDataSchema.get_db().view(
        'schemas_by_xmlns_or_case_type/view',
        startkey=key,
        endkey=key + [{}],
        include_docs=False,
        limit=1,
    ).first()
    return result['id'] if result else None
