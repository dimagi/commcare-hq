import json

from django.test import SimpleTestCase

from corehq.apps.export.export import (
    _write_export_file,
    get_export_file,
)
from corehq.apps.export.models import (
    TableConfiguration,
    ExportColumn,
    ScalarItem,
)
from corehq.apps.export.models.new import (
    ExportInstance,
    ExportItem,
    CaseExportInstance,
)
from corehq.apps.export.tests.util import new_case, DOMAIN, DEFAULT_CASE_TYPE
from corehq.pillows.case import CasePillow
from corehq.util.elastic import ensure_index_deleted
from couchexport.models import Format
from pillowtop.es_utils import completely_initialize_pillow_index


class WriterTest(SimpleTestCase):

    docs = [
        {
            "form": {
                "q1": "foo",
                "q2": {
                    "q4": "bar",
                },
                "q3": "baz"
            }
        },
        {
            "form": {
                "q1": "bip",
                "q2": {
                    "q4": "boop",
                },
                "q3": "bop"
            }
        },
    ]

    def test_simple_table(self):
        """
        Confirm that some simple documents and a simple ExportInstance
        are writtern with _write_export_file() correctly
        """

        export_instance = ExportInstance(
            export_format=Format.JSON,
            tables=[
                TableConfiguration(
                    name="My table",
                    columns=[
                        ExportColumn(
                            label="Q3",
                            item=ScalarItem(
                                path=['form', 'q3'],
                            ),
                            selected=True
                        ),
                        ExportColumn(
                            label="Q1",
                            item=ScalarItem(
                                path=['form', 'q1'],
                            ),
                            selected=True
                        ),
                    ]
                )
            ]
        )

        with _write_export_file(export_instance, self.docs) as export:
            self.assertEqual(
                json.loads(export),
                {
                    u'My table': {
                        u'headers': [u'Q3', u'Q1'],
                        u'rows': [[u'baz', u'foo'], [u'bop', u'bip']],

                    }
                }
            )

    def test_multi_table(self):
        export_instance = ExportInstance(
            export_format=Format.JSON,
            tables=[
                TableConfiguration(
                    name="My table",
                    path=[],
                    columns=[
                        ExportColumn(
                            label="Q3",
                            item=ScalarItem(
                                path=['form', 'q3'],
                            ),
                            selected=True,
                        ),
                    ]
                ),
                TableConfiguration(
                    name="My other table",
                    path=['form', 'q2'],
                    columns=[
                        ExportColumn(
                            label="Q4",
                            item=ScalarItem(
                                path=['form', 'q2', 'q4'],
                            ),
                            selected=True,
                        ),
                    ]
                )
            ]
        )

        with _write_export_file(export_instance, self.docs) as export:
            self.assertEqual(
                json.loads(export),
                {
                    u'My table': {
                        u'headers': [u'Q3'],
                        u'rows': [[u'baz'], [u'bop']],

                    },
                    u'My other table': {
                        u'headers': [u'Q4'],
                        u'rows': [[u'bar'], [u'boop']],
                    }
                }
            )


class ExportTest(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        cls.case_pillow = CasePillow(online=False)
        completely_initialize_pillow_index(cls.case_pillow)

        case = new_case(foo="apple", bar="banana")
        cls.case_pillow.send_robust(case.to_json())

        case = new_case(owner_id="some_other_owner", foo="apple", bar="banana")
        cls.case_pillow.send_robust(case.to_json())

        case = new_case(type="some_other_type", foo="apple", bar="banana")
        cls.case_pillow.send_robust(case.to_json())

        case = new_case(closed=True, foo="apple", bar="banana")
        cls.case_pillow.send_robust(case.to_json())

        cls.case_pillow.get_es_new().indices.refresh(cls.case_pillow.es_index)

    @classmethod
    def tearDownClass(cls):
        ensure_index_deleted(cls.case_pillow.es_index)

    def test_get_export_file(self):
        export_file = get_export_file(
            CaseExportInstance(
                export_format=Format.JSON,
                domain=DOMAIN,
                case_type=DEFAULT_CASE_TYPE,
                tables=[TableConfiguration(
                    name="My table",
                    path=[],
                    columns=[
                        ExportColumn(
                            label="Foo column",
                            item=ExportItem(
                                path=["foo"]
                            ),
                            selected=True,
                        ),
                        ExportColumn(
                            label="Bar column",
                            item=ExportItem(
                                path=["bar"]
                            ),
                            selected=True,
                        )
                    ]
                )]
            ),
            []  # No filters
        )
        with export_file as export:
            self.assertEqual(
                json.loads(export),
                {
                    u'My table': {
                        u'headers': [
                            u'Foo column',
                            u'Bar column'],
                        u'rows': [
                            [u'apple', u'banana'],
                            [u'apple', u'banana'],
                            [u'apple', u'banana'],
                        ],
                    }
                }
            )
