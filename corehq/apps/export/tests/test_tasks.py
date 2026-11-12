from unittest.mock import ANY, patch

import pytest

from corehq.apps.export.const import CASE_EXPORT, FORM_EXPORT
from corehq.apps.export.models import CaseExportDataSchema, FormExportDataSchema
from corehq.apps.export.tasks import build_export_schema


@pytest.mark.parametrize("export_type, schema_cls", [
    (CASE_EXPORT, CaseExportDataSchema), (FORM_EXPORT, FormExportDataSchema),
])
def test_build_export_schema_calls_generate(export_type, schema_cls):
    fake = schema_cls(_id='schema-1')
    with patch.object(schema_cls, 'generate_schema_from_builds', return_value=fake) as gen:
        result = build_export_schema.delay(export_type, 'd', 'app', 'ident', True).get()
    assert result == {'schema_id': 'schema-1'}
    gen.assert_called_once_with(
        'd', 'app', 'ident',
        only_process_current_builds=True, task=ANY, for_new_export_instance=True,
    )


def test_build_export_schema_counts_failure():
    with (
        patch.object(CaseExportDataSchema, 'generate_schema_from_builds', side_effect=ValueError),
        patch('corehq.apps.export.tasks.metrics_counter') as counter,
        pytest.raises(ValueError),
    ):
        build_export_schema.apply(args=(CASE_EXPORT, 'd', None, 'ident', True)).get()
    counter.assert_called_once_with('commcare.exports.schema_build', tags={'outcome': 'failed'})
