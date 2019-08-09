from __future__ import absolute_import, unicode_literals

from django.test import TestCase

from corehq.apps.export.const import CASE_ID_TO_LINK, FORM_ID_TO_LINK
from corehq.apps.export.models import (
    CaseExportInstance,
    ExportColumn,
    ExportInstance,
    ExportItem,
    FormExportInstance,
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
                    selected=True,
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
                    selected=True,
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
    
    def test_caseid_column_label(self):
        export_with_modified_caseid_column = CaseExportInstance(
            is_odata_config=True,
            tables=[
                TableConfiguration(
                    selected=True,
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
                    selected=True,
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

    def test_ignore_case_link_label(self):
        export_with_case_link = CaseExportInstance(
            is_odata_config=True,
            tables=[
                TableConfiguration(
                    selected=True,
                    columns=[
                        ExportColumn(
                            label='my_case_link',
                            item=ExportItem(
                                path=[
                                    PathNode(name='_id')
                                ],
                                transform=CASE_ID_TO_LINK,
                            ),
                            selected=True,
                        )
                    ]
                )
            ]
        )
        export_with_case_link.save()
        self.addCleanup(export_with_case_link.delete)
        cleaned_export = CaseExportInstance.get(export_with_case_link.get_id)
        self.assertEqual(cleaned_export.tables[0].columns[0].label, 'my_case_link')

    def test_ignore_form_link_label(self):
        export_with_form_link = FormExportInstance(
            is_odata_config=True,
            tables=[
                TableConfiguration(
                    selected=True,
                    columns=[
                        ExportColumn(
                            label='my_form_link',
                            item=ExportItem(
                                path=[
                                    PathNode(name='form'),
                                    PathNode(name='meta'),
                                    PathNode(name='instanceID')
                                ],
                                transform=FORM_ID_TO_LINK,
                            ),
                            selected=True,
                        )
                    ]
                )
            ]
        )
        export_with_form_link.save()
        self.addCleanup(export_with_form_link.delete)
        cleaned_export = FormExportInstance.get(export_with_form_link.get_id)
        self.assertEqual(cleaned_export.tables[0].columns[0].label, 'my_form_link')
