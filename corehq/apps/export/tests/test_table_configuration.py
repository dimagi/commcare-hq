from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase

from corehq.apps.export.const import USERNAME_TRANSFORM
from corehq.apps.export.models import (
    DocRow,
    RowNumberColumn,
    PathNode,
    ExportRow,
    ScalarItem,
    ExportColumn,
    TableConfiguration,
)


class TableConfigurationTest(SimpleTestCase):

    def test_get_column(self):
        table_configuration = TableConfiguration(
            path=[PathNode(name='form', is_repeat=False), PathNode(name="repeat1", is_repeat=True)],
            columns=[
                ExportColumn(
                    item=ScalarItem(
                        path=[
                            PathNode(name='form'),
                            PathNode(name='repeat1', is_repeat=True),
                            PathNode(name='q1')
                        ],
                    )
                ),
                ExportColumn(
                    item=ScalarItem(
                        path=[
                            PathNode(name="form"),
                            PathNode(name="user_id"),
                        ],
                        transform=USERNAME_TRANSFORM
                    )
                ),
                ExportColumn(
                    item=ScalarItem(
                        path=[
                            PathNode(name='form'),
                            PathNode(name='repeat1', is_repeat=True),
                            PathNode(name='q2')
                        ],
                    )
                ),
            ]
        )

        index, column = table_configuration.get_column(
            [
                PathNode(name='form'),
                PathNode(name='repeat1', is_repeat=True),
                PathNode(name='q1')
            ],
            'ScalarItem',
            None,
        )
        self.assertEqual(
            column.item.path,
            [
                PathNode(name='form'),
                PathNode(name='repeat1', is_repeat=True),
                PathNode(name='q1')
            ]
        )
        self.assertEqual(index, 0)

        index, column = table_configuration.get_column(
            [
                PathNode(name='form'),
                PathNode(name='repeat1', is_repeat=True),
                PathNode(name='DoesNotExist')
            ],
            'ScalarItem',
            None,
        )
        self.assertIsNone(column)

        # Verify that get_column ignores deid transforms
        index, column = table_configuration.get_column(
            [PathNode(name="form"), PathNode(name="user_id")],
            'ScalarItem',
            USERNAME_TRANSFORM
        )
        self.assertIsNotNone(column)
        self.assertEqual(index, 1)


class TableConfigurationGetSubDocumentsTest(SimpleTestCase):

    def test_basic(self):

        table = TableConfiguration(path=[])
        self.assertEqual(
            table._get_sub_documents(
                {'foo': 'a'},
                0
            ),
            [
                DocRow(row=(0,), doc={'foo': 'a'})
            ]
        )

    def test_simple_repeat(self):
        table = TableConfiguration(
            path=[PathNode(name="foo", is_repeat=True)]
        )
        self.assertEqual(
            table._get_sub_documents(
                {
                    'foo': [
                        {'bar': 'a'},
                        {'bar': 'b'},
                    ]
                },
                0
            ),
            [
                DocRow(row=(0, 0), doc={'bar': 'a'}),
                DocRow(row=(0, 1), doc={'bar': 'b'})
            ]
        )

    def test_nested_repeat(self):
        table = TableConfiguration(
            path=[PathNode(name='foo', is_repeat=True), PathNode(name='bar', is_repeat=True)],
        )
        self.assertEqual(
            table._get_sub_documents(
                {
                    'foo': [
                        {
                            'bar': [
                                {'baz': 'a'},
                                {'baz': 'b'}
                            ],
                        },
                        {
                            'bar': [
                                {'baz': 'c'}
                            ],
                        },
                    ],
                },
                0
            ),
            [
                DocRow(row=(0, 0, 0), doc={'baz': 'a'}),
                DocRow(row=(0, 0, 1), doc={'baz': 'b'}),
                DocRow(row=(0, 1, 0), doc={'baz': 'c'}),
            ]
        )

    def test_single_iteration_repeat(self):
        table = TableConfiguration(
            path=[PathNode(name='group1', is_repeat=False), PathNode(name='repeat1', is_repeat=True)],
        )
        self.assertEqual(
            table._get_sub_documents(
                {
                    'group1': {
                        'repeat1': {
                            'baz': 'a'
                        },
                    }
                },
                0
            ),
            [
                DocRow(row=(0, 0), doc={'baz': 'a'}),
            ]
        )


class TableConfigurationGetRowsTest(SimpleTestCase):

    def test_simple(self):
        table_configuration = TableConfiguration(
            path=[],
            columns=[
                ExportColumn(
                    item=ScalarItem(
                        path=[PathNode(name='form'), PathNode(name='q3')],
                    ),
                    selected=True,
                ),
                ExportColumn(
                    item=ScalarItem(
                        path=[PathNode(name='form'), PathNode(name='q1')],
                    ),
                    selected=True,
                ),
                ExportColumn(
                    item=ScalarItem(
                        path=[PathNode(name='form'), PathNode(name='q2')],
                    ),
                    selected=False,
                ),
            ]
        )
        submission = {
            'domain': 'my-domain',
            '_id': '1234',
            "form": {
                "q1": "foo",
                "q2": "bar",
                "q3": "baz"
            }
        }
        self.assertEqual(
            [row.data for row in table_configuration.get_rows(submission, 0)],
            [['baz', 'foo']]
        )

    def test_repeat(self):
        table_configuration = TableConfiguration(
            path=[PathNode(name="form", is_repeat=False), PathNode(name="repeat1", is_repeat=True)],
            columns=[
                ExportColumn(
                    item=ScalarItem(
                        path=[
                            PathNode(name="form"),
                            PathNode(name="repeat1", is_repeat=True),
                            PathNode(name="q1")
                        ],
                    ),
                    selected=True,
                ),
            ]
        )
        submission = {
            'domain': 'my-domain',
            '_id': '1234',
            'form': {
                'repeat1': [
                    {'q1': 'foo'},
                    {'q1': 'bar'}
                ]
            }
        }
        self.assertEqual(
            [row.data for row in table_configuration.get_rows(submission, 0)],
            [ExportRow(['foo']).data, ExportRow(['bar']).data]
        )

    def test_double_repeat(self):
        table_configuration = TableConfiguration(
            path=[
                PathNode(name="form", is_repeat=False),
                PathNode(name="repeat1", is_repeat=True),
                PathNode(name="group1", is_repeat=False),
                PathNode(name="repeat2", is_repeat=True),
            ],
            columns=[
                RowNumberColumn(
                    selected=True
                ),
                ExportColumn(
                    item=ScalarItem(
                        path=[
                            PathNode(name='form'),
                            PathNode(name='repeat1', is_repeat=True),
                            PathNode(name='group1'),
                            PathNode(name='repeat2', is_repeat=True),
                            PathNode(name='q1')
                        ],
                    ),
                    selected=True,
                ),
            ]
        )
        submission = {
            'domain': 'my-domain',
            '_id': '1234',
            'form': {
                'repeat1': [
                    {
                        'group1': {
                            'repeat2': [
                                {'q1': 'foo'},
                                {'q1': 'bar'}
                            ]
                        }
                    },
                    {
                        'group1': {
                            'repeat2': [
                                {'q1': 'beep'},
                                {'q1': 'boop'}
                            ]
                        }
                    },
                ]
            }
        }
        self.assertEqual(
            [row.data for row in table_configuration.get_rows(submission, 0)],
            [
                ["0.0.0", 0, 0, 0, 'foo'],
                ["0.0.1", 0, 0, 1, 'bar'],
                ["0.1.0", 0, 1, 0, 'beep'],
                ["0.1.1", 0, 1, 1, 'boop']
            ]
        )

    def test_empty_group(self):
        table_configuration = TableConfiguration(
            path=[
                PathNode(name="form", is_repeat=False),
                PathNode(name="group", is_repeat=False),
                PathNode(name="repeat1", is_repeat=True)
            ],
            columns=[
                ExportColumn(
                    item=ScalarItem(
                        path=[
                            PathNode(name="form"),
                            PathNode(name="group"),
                            PathNode(name="repeat1", is_repeat=True),
                            PathNode(name="q1")
                        ],
                    ),
                    selected=True,
                ),
            ]
        )
        submission = {
            'domain': 'my-domain',
            '_id': '1234',
            'form': {
                'group': ''
            }
        }
        self.assertEqual(
            [row.data for row in table_configuration.get_rows(submission, 0)], []
        )
