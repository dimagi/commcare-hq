import json

from StringIO import StringIO
from django.test import SimpleTestCase
from elasticsearch.exceptions import ConnectionError
from openpyxl import load_workbook

from corehq.apps.export.export import (
    _get_tables,
    _get_writer,
    _Writer,
    _write_export_instance,
    ExportFile,
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
    PathNode,
    MAIN_TABLE
)
from corehq.apps.export.tests.util import (
    new_case,
    DOMAIN,
    DEFAULT_CASE_TYPE,
)
from corehq.pillows.case import CasePillow
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup
from couchexport.export import get_writer
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
                    label="My table",
                    columns=[
                        ExportColumn(
                            label="Q3",
                            item=ScalarItem(
                                path=[PathNode(name='form'), PathNode(name='q3')],
                            ),
                            selected=True
                        ),
                        ExportColumn(
                            label="Q1",
                            item=ScalarItem(
                                path=[PathNode(name='form'), PathNode(name='q1')],
                            ),
                            selected=True
                        ),
                    ]
                )
            ]
        )

        writer = _get_writer([export_instance])
        with writer.open(export_instance.tables):
            _write_export_instance(writer, export_instance, self.docs)

        with ExportFile(writer.path, writer.format) as export:
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
                    label="My table",
                    path=[],
                    columns=[
                        ExportColumn(
                            label="Q3",
                            item=ScalarItem(
                                path=[PathNode(name='form'), PathNode(name='q3')],
                            ),
                            selected=True,
                        ),
                    ]
                ),
                TableConfiguration(
                    label="My other table",
                    path=[PathNode(name='form', is_repeat=False), PathNode(name="q2", is_repeat=False)],
                    columns=[
                        ExportColumn(
                            label="Q4",
                            item=ScalarItem(
                                path=[PathNode(name='form'), PathNode(name='q2'), PathNode(name='q4')],
                            ),
                            selected=True,
                        ),
                    ]
                )
            ]
        )
        writer = _get_writer([export_instance])
        with writer.open(export_instance.tables):
            _write_export_instance(writer, export_instance, self.docs)
        with ExportFile(writer.path, writer.format) as export:
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

    def test_multiple_write_export_instance_calls(self):
        """
        Confirm that calling _write_export_instance() multiple times
        (as part of a bulk export) works as expected.
        """
        export_instances = [
            ExportInstance(
                # export_format=Format.JSON,
                tables=[
                    TableConfiguration(
                        label="My table",
                        path=[],
                        columns=[
                            ExportColumn(
                                label="Q3",
                                item=ScalarItem(
                                    path=[PathNode(name='form'), PathNode(name='q3')],
                                ),
                                selected=True,
                            ),
                        ]
                    ),
                ]
            ),
            ExportInstance(
                # export_format=Format.JSON,
                tables=[
                    TableConfiguration(
                        label="My other table",
                        path=[PathNode(name="form", is_repeat=False), PathNode(name="q2", is_repeat=False)],
                        columns=[
                            ExportColumn(
                                label="Q4",
                                item=ScalarItem(
                                    path=[PathNode(name='form'), PathNode(name='q2'), PathNode(name='q4')],
                                ),
                                selected=True,
                            ),
                        ]
                    )
                ]
            )

        ]

        writer = _Writer(get_writer(Format.JSON))
        with writer.open(_get_tables(export_instances)):
            _write_export_instance(writer, export_instances[0], self.docs)
            _write_export_instance(writer, export_instances[1], self.docs)

        with ExportFile(writer.path, writer.format) as export:
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
        with trap_extra_setup(ConnectionError, msg="cannot connect to elasicsearch"):
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
            [
                CaseExportInstance(
                    export_format=Format.JSON,
                    domain=DOMAIN,
                    case_type=DEFAULT_CASE_TYPE,
                    tables=[TableConfiguration(
                        label="My table",
                        path=[],
                        columns=[
                            ExportColumn(
                                label="Foo column",
                                item=ExportItem(
                                    path=[PathNode(name="foo")]
                                ),
                                selected=True,
                            ),
                            ExportColumn(
                                label="Bar column",
                                item=ExportItem(
                                    path=[PathNode(name="bar")]
                                ),
                                selected=True,
                            )
                        ]
                    )]
                ),
            ],
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

    def test_simple_bulk_export(self):

        export_file = get_export_file(
            [
                CaseExportInstance(
                    export_format=Format.JSON,
                    domain=DOMAIN,
                    case_type=DEFAULT_CASE_TYPE,
                    tables=[TableConfiguration(
                        label="My table",
                        path=MAIN_TABLE,
                        columns=[
                            ExportColumn(
                                label="Foo column",
                                item=ExportItem(
                                    path=[PathNode(name="foo")]
                                ),
                                selected=True,
                            ),
                        ]
                    )]
                ),
                CaseExportInstance(
                    export_format=Format.JSON,
                    domain=DOMAIN,
                    case_type=DEFAULT_CASE_TYPE,
                    tables=[TableConfiguration(
                        label="My table",
                        path=MAIN_TABLE,
                        columns=[
                            ExportColumn(
                                label="Bar column",
                                item=ExportItem(
                                    path=[PathNode(name="bar")]
                                ),
                                selected=True,
                            )
                        ]
                    )]
                ),
            ],
            []  # No filters
        )

        expected = {
            'My table': {
                "A1": "Foo column",
                "A2": "apple",
                "A3": "apple",
                "A4": "apple",
            },
            "My table1": {
                "A1": "Bar column",
                "A2": "banana",
                "A3": "banana",
                "A4": "banana",
            },
        }

        with export_file as export:
            wb = load_workbook(StringIO(export))
            self.assertEqual(wb.get_sheet_names(), ["My table", "My table1"])

            for sheet in expected.keys():
                for cell in expected[sheet].keys():
                    self.assertEqual(
                        wb[sheet][cell].value,
                        expected[sheet][cell],
                        'AssertionError: Sheet "{}", cell "{}" expected: "{}", got "{}"'.format(
                            sheet, cell, expected[sheet][cell], wb[sheet][cell].value
                        )
                    )


class TableHeaderTest(SimpleTestCase):
    def test_deid_column_headers(self):
        col = ExportColumn(
            label="my column",
            deid_transform="deid_id",
        )
        self.assertEqual(col.get_headers(), ["my column [sensitive]"])
