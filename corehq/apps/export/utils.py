from couchdbkit.exceptions import ResourceNotFound
from corehq.apps.export.models import FormQuestionSchema


def get_or_create_question_schema(domain, app_id, xmlns, schema_id=None):
    schema = None
    if schema_id:
        try:
            schema = FormQuestionSchema.get(schema_id)
        except ResourceNotFound:
            pass

    if not schema:
        schemas = FormQuestionSchema.view(
            'form_question_schema/by_xmlns',
            key=[domain, app_id, xmlns],
            include_docs=True
        ).all()

        try:
            schema = schemas[0]
        except IndexError:
            schema = None

        if len(schemas) > 1:
            for dupe in schemas[1:]:
                dupe.delete()

        if not schema:
            schema = FormQuestionSchema(domain=domain, app_id=app_id, xmlns=xmlns)
            schema.save()

    return schema
