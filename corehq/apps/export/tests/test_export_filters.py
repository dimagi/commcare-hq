import uuid

from django.test import SimpleTestCase
from elasticsearch.exceptions import ConnectionError

from corehq.apps.export.esaccessors import get_case_export_base_query
from corehq.apps.export.export import (
    _get_export_documents,
)
from corehq.apps.export.filters import (
    GroupOwnerFilter,
    IsClosedFilter,
    OwnerFilter,
    OR,
    FormSubmittedByFilter,
)
from corehq.apps.export.models.new import (
    CaseExportInstance,
    FormExportInstance)
from corehq.apps.export.tests.util import (

    DEFAULT_USER,
    DEFAULT_CASE_TYPE,
    DEFAULT_XMLNS,
    DEFAULT_APP_ID,
    DOMAIN,
    new_case,
    new_form,
)
from corehq.apps.groups.models import Group
from corehq.pillows.case import CasePillow
from corehq.pillows.group import GroupPillow
from corehq.pillows.xform import XFormPillow
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup
from pillowtop.es_utils import completely_initialize_pillow_index


class ExportFilterTest(SimpleTestCase):

    def test_or_filter(self):
        self.assertEqual(
            OR(OwnerFilter("foo"), OwnerFilter("bar")).to_es_filter(),
            {
                'or': (
                    {'term': {'owner_id': 'foo'}},
                    {'term': {'owner_id': 'bar'}}
                )
            }
        )


class ExportFilterResultTest(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        form_pillow = XFormPillow(online=False)
        case_pillow = CasePillow(online=False)
        group_pillow = GroupPillow(online=False)
        cls.pillows = [form_pillow, case_pillow, group_pillow]

        with trap_extra_setup(ConnectionError, msg="cannot connect to elasicsearch"):
            for pillow in cls.pillows:
                completely_initialize_pillow_index(pillow)

        case = new_case(closed=True)
        case_pillow.send_robust(case.to_json())

        case = new_case(closed=False)
        case_pillow.send_robust(case.to_json())

        case = new_case(closed=True, owner_id="foo")
        case_pillow.send_robust(case.to_json())

        case = new_case(closed=False, owner_id="bar")
        case_pillow.send_robust(case.to_json())

        group = Group(_id=uuid.uuid4().hex, users=["foo", "bar"])
        cls.group_id = group.get_id
        group_pillow.send_robust(group.to_json())

        form = new_form(form={"meta": {"userID": None}})
        form_pillow.send_robust(form.to_json())

        form = new_form(form={"meta": {"userID": ""}})
        form_pillow.send_robust(form.to_json())

        form = new_form(form={"meta": {"deviceID": "abc"}})
        form_pillow.send_robust(form.to_json())

        form = new_form(form={"meta": {"userID": uuid.uuid4().hex}})
        form_pillow.send_robust(form.to_json())



        for pillow in cls.pillows:
            pillow.get_es_new().indices.refresh(pillow.es_index)

    @classmethod
    def tearDownClass(cls):
        for pillow in cls.pillows:
            ensure_index_deleted(pillow.es_index)

    def test_filter_combination(self):
        owner_filter = OwnerFilter(DEFAULT_USER)
        closed_filter = IsClosedFilter(False)
        doc_generator = _get_export_documents(
            CaseExportInstance(domain=DOMAIN, case_type=DEFAULT_CASE_TYPE),
            [owner_filter, closed_filter]
        )
        self.assertEqual(1, len([x for x in doc_generator]))

    def test_group_filters(self):
        group_filter = GroupOwnerFilter(self.group_id)
        doc_generator = _get_export_documents(
            CaseExportInstance(domain=DOMAIN, case_type=DEFAULT_CASE_TYPE),
            [group_filter]
        )
        self.assertEqual(2, len([x for x in doc_generator]))

    def test_get_case_export_base_query(self):
        q = get_case_export_base_query(DOMAIN, DEFAULT_CASE_TYPE)
        result = q.run()
        self.assertEqual(4, len(result.hits))
