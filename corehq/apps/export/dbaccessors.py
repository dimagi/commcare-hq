

def get_latest_export_schema_id(domain, doc_type, xmlns_or_case_type):
    from .models import ExportDataSchema
    result = ExportDataSchema.get_db().view(
        'schemas_by_xmlns_or_case_type/view',
        startkey=[domain, doc_type, xmlns_or_case_type],
        endkey=[domain, doc_type, xmlns_or_case_type, {}],
        include_docs=False,
    ).first()
    return result['id'] if result else None
