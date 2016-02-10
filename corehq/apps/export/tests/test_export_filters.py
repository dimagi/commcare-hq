import uuid

from django.test import SimpleTestCase

from corehq.apps.export.esaccessors import get_case_export_base_query
from corehq.apps.export.export import (
    _get_export_documents,
)
from corehq.apps.export.filters import (
    GroupOwnerFilter,
    IsClosedFilter,
    OwnerFilter,
)
from corehq.apps.export.models.new import (
    CaseExportInstance,
)
from corehq.apps.export.tests.util import new_case, DEFAULT_USER, DOMAIN, \
    DEFAULT_CASE_TYPE
from corehq.apps.groups.models import Group
from corehq.pillows.case import CasePillow
from corehq.pillows.group import GroupPillow
from corehq.util.elastic import ensure_index_deleted
from pillowtop.es_utils import completely_initialize_pillow_index


class ExportFilterTest(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        case_pillow = CasePillow(online=False)
        group_pillow = GroupPillow(online=False)
        cls.pillows = [case_pillow, group_pillow]

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
