from __future__ import absolute_import
from __future__ import unicode_literals

from django.test import TestCase

from corehq.apps.export.models import (
    CaseExportInstance,
    FormExportInstance,
    ExportColumn,
    ExportInstance,
    ExportItem,
    PathNode,
    RowNumberColumn,
    TableConfiguration,
)


class TestODataWrap(TestCase):

    def test_column_label_containing_period(self):
        export_with_column_containing_period = ExportInstance(
            is_odata_config=True,
            tables=[
                TableConfiguration(
                    columns=[
                        ExportColumn(
                            label='.label',
                            item=ExportItem(
                                path=[
                                    PathNode(name='val')
                                ]
                            ),
                            selected=True,
                        )
                    ]
                )
            ]
        )
        export_with_column_containing_period.save()
        self.addCleanup(export_with_column_containing_period.delete)
        cleaned_export = ExportInstance.get(export_with_column_containing_period.get_id)
        self.assertEqual(cleaned_export.tables[0].columns[0].label, ' label')

    def test_column_label_containing_at_sign(self):
        export_with_column_containing_at_sign = ExportInstance(
            is_odata_config=True,
            tables=[
                TableConfiguration(
                    columns=[
                        ExportColumn(
                            label='@label',
                            item=ExportItem(
                                path=[
                                    PathNode(name='val')
                                ]
                            ),
                            selected=True,
                        )
                    ]
                )
            ]
        )
        export_with_column_containing_at_sign.save()
        self.addCleanup(export_with_column_containing_at_sign.delete)
        cleaned_export = ExportInstance.get(export_with_column_containing_at_sign.get_id)
        self.assertEqual(cleaned_export.tables[0].columns[0].label, 'label')

    def test_row_number_column_is_removed(self):
        export_with_row_number_column = ExportInstance(
            is_odata_config=True,
            tables=[
                TableConfiguration(
                    columns=[
                        RowNumberColumn(
                            label='row-number',
                        ),
                        ExportColumn(
                            label='label',
                            item=ExportItem(
                                path=[
                                    PathNode(name='val')
                                ]
                            ),
                            selected=True,
                        )
                    ]
                )
            ]
        )
        export_with_row_number_column.save()
        self.addCleanup(export_with_row_number_column.delete)
        cleaned_export = ExportInstance.get(export_with_row_number_column.get_id)
        tables = cleaned_export.tables
        self.assertEqual(len(tables), 1)
        columns = tables[0].columns
        self.assertEqual(len(columns), 1)
        self.assertFalse(isinstance(columns[0], RowNumberColumn))
        self.assertEqual(columns[0].label, 'label')

    def test_caseid_column_label(self):
        export_with_modified_caseid_column = CaseExportInstance(
            is_odata_config=True,
            tables=[
                TableConfiguration(
                    columns=[
                        ExportColumn(
                            label='modified_case_id_column',
                            item=ExportItem(
                                path=[
                                    PathNode(name='_id')
                                ]
                            ),
                            selected=True,
                        )
                    ]
                )
            ]
        )
        export_with_modified_caseid_column.save()
        self.addCleanup(export_with_modified_caseid_column.delete)
        cleaned_export = CaseExportInstance.get(export_with_modified_caseid_column.get_id)
        self.assertEqual(cleaned_export.tables[0].columns[0].label, 'caseid')

    def test_formid_column_label(self):
        export_with_modified_formid_column = FormExportInstance(
            is_odata_config=True,
            tables=[
                TableConfiguration(
                    columns=[
                        ExportColumn(
                            label='modified_form_id_column',
                            item=ExportItem(
                                path=[
                                    PathNode(name='form'),
                                    PathNode(name='meta'),
                                    PathNode(name='instanceID')
                                ]
                            ),
                            selected=True,
                        )
                    ]
                )
            ]
        )
        export_with_modified_formid_column.save()
        self.addCleanup(export_with_modified_formid_column.delete)
        cleaned_export = FormExportInstance.get(export_with_modified_formid_column.get_id)
        self.assertEqual(cleaned_export.tables[0].columns[0].label, 'formid')
