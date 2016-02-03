import uuid

from django.test import SimpleTestCase, TestCase

from casexml.apps.case.models import CommCareCase
from corehq.apps.export.export import (
    _write_export_file,
    _get_case_export_base_query,
    get_export_file,
    _get_export_documents,
)
from corehq.apps.export.filters import OwnerFilter, IsClosedFilter
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
from corehq.pillows.case import CasePillow
from corehq.util.elastic import delete_es_index
from couchexport.models import Format
from pillowtop.es_utils import completely_initialize_pillow_index


DOMAIN = "export-file-domain"
DEFAULT_USER = "user1"
DEFAULT_CASE_TYPE = "test-case-type"
DEFAULT_CASE_NAME = "a case"


def new_case(domain=DOMAIN, user_id=DEFAULT_USER, owner_id=DEFAULT_USER,
             type=DEFAULT_CASE_TYPE, name=DEFAULT_CASE_NAME,
             closed=False, **kwargs):
    kwargs["_id"] = kwargs.get("_id", uuid.uuid4().hex)
    return CommCareCase(
        domain=domain,
        user_id=user_id,
        owner_id=owner_id,
        type=type,
        name=name,
        closed=closed,
        **kwargs
    )


class WriterTest(SimpleTestCase):

    def test_simple(self):
        """
        Confirm that some simple documents and a simple ExportInstance
        are writtern with _write_export_file() correctly
        """

        export_instance = ExportInstance(
            format=Format.PYTHON_DICT,
            tables=[
                TableConfiguration(
                    name="My table",
                    columns=[
                        ExportColumn(
                            label="Q3",
                            item=ScalarItem(
                                path=['form', 'q3'],
                            )
                        ),
                        ExportColumn(
                            label="Q1",
                            item=ScalarItem(
                                path=['form', 'q1'],
                            )
                        ),
                    ]
                )
            ]
        )
        docs = [
            {
                "form": {
                    "q1": "foo",
                    "q2": "bar",
                    "q3": "baz"
                }
            },
            {
                "form": {
                    "q1": "bip",
                    "q2": "boop",
                    "q3": "bop"
                }
            },
        ]
        self.assertEqual(
            _write_export_file(export_instance, docs),
            [
                {
                    u'headers': [u'Q3', u'Q1'],
                    u'rows': [[u'baz', u'foo'], [u'bop', u'bip']],
                    u'table_name': u'My table'
                }
            ]
        )


class ExportTest(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        cls.pillow = CasePillow(online=False)
        completely_initialize_pillow_index(cls.pillow)

        case = new_case(foo="apple", bar="banana")
        cls.pillow.send_robust(case.to_json())

        case = new_case(owner_id="some_other_owner", foo="apple", bar="banana")
        cls.pillow.send_robust(case.to_json())

        case = new_case(type="some_other_type", foo="apple", bar="banana")
        cls.pillow.send_robust(case.to_json())

        case = new_case(closed=True, foo="apple", bar="banana")
        cls.pillow.send_robust(case.to_json())

        cls.pillow.get_es_new().indices.refresh(cls.pillow.es_index)

    @classmethod
    def tearDownClass(cls):
        delete_es_index(cls.pillow.es_index)

    def test_get_export_file(self):
        export = get_export_file(
            CaseExportInstance(
                format=Format.PYTHON_DICT,
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
                            )
                        ),
                        ExportColumn(
                            label="Bar column",
                            item=ExportItem(
                                path=["bar"]
                            )
                        )
                    ]
                )]
            ),
            []  # No filters
        )
        self.assertEqual(
            export,
            [
                {
                    u'table_name': u'My table',
                    u'headers': [
                        u'Foo column',
                        u'Bar column'],
                    u'rows': [
                        [u'apple', u'banana'],
                        [u'apple', u'banana'],
                        [u'apple', u'banana'],
                    ],
                    
                }
            ]
        )

    def test_filters(self):
        # TODO: Test other filters
        owner_filter = OwnerFilter(DEFAULT_USER)
        closed_filter = IsClosedFilter(False)
        self.assertEqual(
            1,
            len(
                _get_export_documents(
                    CaseExportInstance(domain=DOMAIN, case_type=DEFAULT_CASE_TYPE),
                    [owner_filter, closed_filter]
                )
            )
        )

    def test_get_case_export_base_query(self):
        q = _get_case_export_base_query(CaseExportInstance(domain=DOMAIN, case_type=DEFAULT_CASE_TYPE))
        result = q.run()
        self.assertEqual(3, len(result.hits))
