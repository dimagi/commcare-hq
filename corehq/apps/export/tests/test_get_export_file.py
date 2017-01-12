import json
from StringIO import StringIO

import re
from django.test import SimpleTestCase
from django.core.cache import cache
from elasticsearch.exceptions import ConnectionError
from mock import patch
from openpyxl import load_workbook

from corehq.apps.export.const import (
    DEID_DATE_TRANSFORM,
    CASE_NAME_TRANSFORM,
)
from corehq.apps.export.export import (
    _get_writer,
    _Writer,
    _write_export_instance,
    ExportFile,
    get_export_file,
)
from corehq.apps.export.const import (
    MISSING_VALUE,
    EMPTY_VALUE,
)
from corehq.apps.export.models import (
    TableConfiguration,
    ExportColumn,
    ScalarItem,
    FormExportInstance,
    ExportItem,
    MultipleChoiceItem,
    SplitExportColumn,
    CaseExportInstance,
    PathNode,
    Option,
    MAIN_TABLE,
    StockItem,
    StockFormExportColumn,
)
from corehq.apps.export.tests.util import (
    new_case,
    DOMAIN,
    DEFAULT_CASE_TYPE,
)
from corehq.elastic import send_to_elasticsearch, get_es_new
from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup
from couchexport.export import get_writer
from couchexport.models import Format
from couchexport.transforms import couch_to_excel_datetime
from pillowtop.es_utils import initialize_index_and_mapping


class WriterTest(SimpleTestCase):

    docs = [
        {
            'domain': 'my-domain',
            '_id': '1234',
            "form": {
                "q1": "foo",
                "q2": {
                    "q4": "bar",
                },
                "q3": "baz",
                "mc": "two extra"
            }
        },
        {
            'domain': 'my-domain',
            '_id': '12345',
            "form": {
                "q1": "bip",
                "q2": {
                    "q4": "boop",
                },
                "q3": "bop",
                "mc": "one two",
                "date": "2015-07-22T14:16:49.584880Z",
            }
        },
    ]

    def test_simple_table(self):
        """
        Confirm that some simple documents and a simple FormExportInstance
        are writtern with _write_export_file() correctly
        """

        export_instance = FormExportInstance(
            export_format=Format.JSON,
            tables=[
                TableConfiguration(
                    label="My table",
                    selected=True,
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
        with writer.open([export_instance]):
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

    def test_split_questions(self):
        """Ensure columns are split when `split_multiselects` is set to True"""
        export_instance = FormExportInstance(
            export_format=Format.JSON,
            domain=DOMAIN,
            case_type=DEFAULT_CASE_TYPE,
            split_multiselects=True,
            tables=[TableConfiguration(
                label="My table",
                selected=True,
                path=[],
                columns=[
                    SplitExportColumn(
                        label="MC",
                        item=MultipleChoiceItem(
                            path=[PathNode(name='form'), PathNode(name='mc')],
                            options=[
                                Option(value='one'),
                                Option(value='two'),
                            ]
                        ),
                        selected=True,
                    )
                ]
            )]
        )
        writer = _get_writer([export_instance])
        with writer.open([export_instance]):
            _write_export_instance(writer, export_instance, self.docs)

        with ExportFile(writer.path, writer.format) as export:
            self.assertEqual(
                json.loads(export),
                {
                    u'My table': {
                        u'headers': [u'MC | one', u'MC | two', 'MC | extra'],
                        u'rows': [[EMPTY_VALUE, 1, 'extra'], [1, 1, '']],

                    }
                }
            )

    def test_form_stock_columns(self):
        """Ensure that we can export stock properties in a form export"""
        docs = [{
            '_id': 'simone-biles',
            'domain': DOMAIN,
            'form': {
                'balance': [
                    {
                        '@type': 'question-id',
                        'entry': {
                            '@quantity': '2',
                        }
                    }, {
                        '@type': 'other-question-id',
                        'entry': {
                            '@quantity': '3',
                        }
                    }]
            },
        }, {
            '_id': 'sam-mikulak',
            'domain': DOMAIN,
            'form': {
                'balance': {
                    '@type': 'question-id',
                    'entry': {
                        '@quantity': '2',
                    }
                },
            },
        }, {
            '_id': 'kerri-walsh',
            'domain': DOMAIN,
            'form': {
                'balance': {
                    '@type': 'other-question-id',
                    'entry': {
                        '@quantity': '2',
                    }
                },
            },
        }, {
            '_id': 'april-ross',
            'domain': DOMAIN,
            'form': {},
        }]
        export_instance = FormExportInstance(
            export_format=Format.JSON,
            domain=DOMAIN,
            tables=[TableConfiguration(
                label="My table",
                selected=True,
                path=[],
                columns=[
                    StockFormExportColumn(
                        label="StockItem @type",
                        item=StockItem(
                            path=[
                                PathNode(name='form'),
                                PathNode(name='balance:question-id'),
                                PathNode(name='@type'),
                            ],
                        ),
                        selected=True,
                    ),
                    StockFormExportColumn(
                        label="StockItem @quantity",
                        item=StockItem(
                            path=[
                                PathNode(name='form'),
                                PathNode(name='balance:question-id'),
                                PathNode(name='entry'),
                                PathNode(name='@quantity'),
                            ],
                        ),
                        selected=True,
                    ),
                ]
            )]
        )
        writer = _get_writer([export_instance])

        with writer.open([export_instance]):
            _write_export_instance(writer, export_instance, docs)

        with ExportFile(writer.path, writer.format) as export:
            self.assertEqual(
                json.loads(export),
                {
                    u'My table': {
                        u'headers': [u'StockItem @type', u'StockItem @quantity'],
                        u'rows': [
                            ['question-id', '2'],
                            ['question-id', '2'],
                            [MISSING_VALUE, MISSING_VALUE],
                            [MISSING_VALUE, MISSING_VALUE],
                        ],
                    }
                }
            )

    def test_transform_dates(self):
        """Ensure dates are transformed for excel when `transform_dates` is set to True"""
        export_instance = FormExportInstance(
            export_format=Format.JSON,
            domain=DOMAIN,
            case_type=DEFAULT_CASE_TYPE,
            transform_dates=True,
            tables=[TableConfiguration(
                label="My table",
                selected=True,
                path=[],
                columns=[
                    ExportColumn(
                        label="Date",
                        item=MultipleChoiceItem(
                            path=[PathNode(name='form'), PathNode(name='date')],
                        ),
                        selected=True,
                    )
                ]
            )]
        )
        writer = _get_writer([export_instance])
        with writer.open([export_instance]):
            _write_export_instance(writer, export_instance, self.docs)

        with ExportFile(writer.path, writer.format) as export:
            self.assertEqual(
                json.loads(export),
                {
                    u'My table': {
                        u'headers': [u'Date'],
                        u'rows': [[MISSING_VALUE], [couch_to_excel_datetime('2015-07-22T14:16:49.584880Z', None)]],

                    }
                }
            )

    def test_split_questions_false(self):
        """Ensure multiselects are not split when `split_multiselects` is set to False"""
        export_instance = FormExportInstance(
            export_format=Format.JSON,
            domain=DOMAIN,
            case_type=DEFAULT_CASE_TYPE,
            split_multiselects=False,
            tables=[TableConfiguration(
                label="My table",
                selected=True,
                path=[],
                columns=[
                    SplitExportColumn(
                        label="MC",
                        item=MultipleChoiceItem(
                            path=[PathNode(name='form'), PathNode(name='mc')],
                            options=[
                                Option(value='one'),
                                Option(value='two'),
                            ]
                        ),
                        selected=True,
                    )
                ]
            )]
        )
        writer = _get_writer([export_instance])
        with writer.open([export_instance]):
            _write_export_instance(writer, export_instance, self.docs)

        with ExportFile(writer.path, writer.format) as export:
            self.assertEqual(
                json.loads(export),
                {
                    u'My table': {
                        u'headers': [u'MC'],
                        u'rows': [['two extra'], ['one two']],

                    }
                }
            )

    def test_multi_table(self):
        export_instance = FormExportInstance(
            export_format=Format.JSON,
            tables=[
                TableConfiguration(
                    label="My table",
                    selected=True,
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
                    selected=True,
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
        with writer.open([export_instance]):
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

    def test_multi_table_order(self):
        tables = [
            TableConfiguration(
                label="My table {}".format(i),
                selected=True,
                path=[],
                columns=[
                    ExportColumn(
                        label="Q{}".format(i),
                        item=ScalarItem(
                            path=[PathNode(name='form'), PathNode(name='q{}'.format(i))],
                        ),
                        selected=True,
                    ),
                ]
            )
            for i in range(10)
        ]
        export_instance = FormExportInstance(
            export_format=Format.HTML,
            tables=tables
        )
        writer = _get_writer([export_instance])
        docs = [
            {
                'domain': 'my-domain',
                '_id': '1234',
                "form": {'q{}'.format(i): 'value {}'.format(i) for i in range(10)}
            }
        ]
        with writer.open([export_instance]):
            _write_export_instance(writer, export_instance, docs)
        with ExportFile(writer.path, writer.format) as export:
            exported_tables = [table for table in re.findall('<h2>(.*)</h2>', export)]

        expected_tables = [t.label for t in tables]
        self.assertEqual(expected_tables, exported_tables)

    def test_multiple_write_export_instance_calls(self):
        """
        Confirm that calling _write_export_instance() multiple times
        (as part of a bulk export) works as expected.
        """
        export_instances = [
            FormExportInstance(
                # export_format=Format.JSON,
                tables=[
                    TableConfiguration(
                        label="My table",
                        selected=True,
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
            FormExportInstance(
                # export_format=Format.JSON,
                tables=[
                    TableConfiguration(
                        label="My other table",
                        selected=True,
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
        with writer.open(export_instances):
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
        super(ExportTest, cls).setUpClass()
        with trap_extra_setup(ConnectionError, msg="cannot connect to elasicsearch"):
            cls.es = get_es_new()
            initialize_index_and_mapping(cls.es, CASE_INDEX_INFO)

        case = new_case(_id='robin', name='batman', foo="apple", bar="banana", date='2016-4-24')
        send_to_elasticsearch('cases', case.to_json())

        case = new_case(owner_id="some_other_owner", foo="apple", bar="banana", date='2016-4-04')
        send_to_elasticsearch('cases', case.to_json())

        case = new_case(type="some_other_type", foo="apple", bar="banana")
        send_to_elasticsearch('cases', case.to_json())

        case = new_case(closed=True, foo="apple", bar="banana")
        send_to_elasticsearch('cases', case.to_json())

        cls.es.indices.refresh(CASE_INDEX_INFO.index)
        cache.clear()

    @classmethod
    def tearDownClass(cls):
        ensure_index_deleted(CASE_INDEX_INFO.index)
        cache.clear()
        super(ExportTest, cls).tearDownClass()

    def test_get_export_file(self):
        export_file = get_export_file(
            [
                CaseExportInstance(
                    export_format=Format.JSON,
                    domain=DOMAIN,
                    case_type=DEFAULT_CASE_TYPE,
                    tables=[TableConfiguration(
                        label="My table",
                        selected=True,
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

    def test_case_name_transform(self):
        docs = [
            {
                'domain': 'my-domain',
                '_id': '1234',
                "form": {
                    "caseid": "robin",
                },
            },
            {
                'domain': 'my-domain',
                '_id': '1234',
                "form": {
                    "caseid": "i-do-not-exist",
                },
            }
        ]
        export_instance = FormExportInstance(
            export_format=Format.JSON,
            tables=[
                TableConfiguration(
                    label="My table",
                    selected=True,
                    columns=[
                        ExportColumn(
                            label="case_name",
                            item=ScalarItem(
                                path=[PathNode(name='form'), PathNode(name='caseid')],
                                transform=CASE_NAME_TRANSFORM,
                            ),
                            selected=True
                        ),
                    ]
                )
            ]
        )
        writer = _get_writer([export_instance])
        with writer.open([export_instance]):
            _write_export_instance(writer, export_instance, docs)

        with ExportFile(writer.path, writer.format) as export:
            self.assertEqual(
                json.loads(export),
                {
                    u'My table': {
                        u'headers': [u'case_name'],
                        u'rows': [[u'batman'], [MISSING_VALUE]],

                    }
                }
            )

    @patch('couchexport.deid.DeidGenerator.random_number', return_value=3)
    def test_export_transforms(self, _):
        export_file = get_export_file(
            [
                CaseExportInstance(
                    export_format=Format.JSON,
                    domain=DOMAIN,
                    case_type=DEFAULT_CASE_TYPE,
                    tables=[TableConfiguration(
                        label="My table",
                        selected=True,
                        path=[],
                        columns=[
                            ExportColumn(
                                label="DEID Date Transform column",
                                item=ExportItem(
                                    path=[PathNode(name="date")]
                                ),
                                selected=True,
                                deid_transform=DEID_DATE_TRANSFORM,
                            )
                        ]
                    )]
                ),
            ],
            []  # No filters
        )
        with export_file as export:
            export_dict = json.loads(export)
            export_dict['My table']['rows'].sort()
            self.assertEqual(
                export_dict,
                {
                    u'My table': {
                        u'headers': [
                            u'DEID Date Transform column [sensitive]',
                        ],
                        u'rows': [
                            [MISSING_VALUE],
                            [u'2016-04-07'],
                            [u'2016-04-27'],  # offset by 3 since that's the mocked random offset
                        ],
                    }
                }
            )

    def test_selected_false(self):
        export_file = get_export_file(
            [
                CaseExportInstance(
                    export_format=Format.JSON,
                    domain=DOMAIN,
                    case_type=DEFAULT_CASE_TYPE,
                    tables=[TableConfiguration(
                        label="My table",
                        selected=False,
                        path=[],
                        columns=[]
                    )]
                ),
            ],
            []  # No filters
        )
        with export_file as export:
            self.assertEqual(json.loads(export), {})

    def test_simple_bulk_export(self):

        export_file = get_export_file(
            [
                CaseExportInstance(
                    export_format=Format.JSON,
                    domain=DOMAIN,
                    case_type=DEFAULT_CASE_TYPE,
                    tables=[TableConfiguration(
                        selected=True,
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
                        selected=True,
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
