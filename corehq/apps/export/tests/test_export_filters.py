from unittest.mock import patch
import uuid

from django.test import SimpleTestCase

from corehq.apps.es.cases import case_adapter
from corehq.apps.es.forms import form_adapter
from corehq.apps.es.groups import group_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.export.esaccessors import get_case_export_base_query
from corehq.apps.export.export import get_export_documents
from corehq.apps.export.filters import (
    OR,
    FormSubmittedByFilter,
    GroupOwnerFilter,
    IsClosedFilter,
    OwnerFilter,
)
from corehq.apps.export.models.new import (
    CaseExportInstance,
    FormExportInstance,
)
from corehq.apps.export.tests.util import (
    DEFAULT_APP_ID,
    DEFAULT_CASE_TYPE,
    DEFAULT_USER,
    DEFAULT_XMLNS,
    DOMAIN,
    new_case,
    new_form,
)
from corehq.apps.groups.models import Group


@es_test
class ExportFilterTest(SimpleTestCase):

    def test_or_filter(self):
        self.assertEqual(
            OR(OwnerFilter("foo"), OwnerFilter("bar")).to_es_filter(),
            {'bool': {'should': ({'term': {'owner_id': 'foo'}},
                                {'term': {'owner_id': 'bar'}})}}
        )


@es_test(
    requires=[case_adapter, form_adapter, group_adapter],
    setup_class=True
)
class ExportFilterResultTest(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with patch('corehq.pillows.utils.get_user_type', return_value='CommCareUser'):
            cases = [
                new_case(closed=True),
                new_case(closed=False),
                new_case(closed=True, owner_id="foo"),
                new_case(closed=False, owner_id="bar"),
            ]
            case_adapter.bulk_index(cases, refresh=True)

            group = Group(_id=uuid.uuid4().hex, users=["foo", "bar"])
            cls.group_id = group._id
            group_adapter.index(group, refresh=True)

            form_json = new_form({"meta": "", "#type": "data"}).to_json()
            # fabricate null userID because convert_form_to_xml will not accept it
            form_json["form"] = {"meta": {"userID": None}}

            forms = [
                form_json,
                new_form({"meta": {"userID": ""}, "#type": "data"}),
                new_form({"meta": {"deviceID": "abc"}, "#type": "data"}),
                new_form({"meta": {"userID": uuid.uuid4().hex}, "#type": "data"})
            ]

            form_adapter.bulk_index(forms, refresh=True)

    def test_filter_combination(self):
        owner_filter = OwnerFilter(DEFAULT_USER)
        closed_filter = IsClosedFilter(False)
        doc_generator = get_export_documents(
            CaseExportInstance(domain=DOMAIN, case_type=DEFAULT_CASE_TYPE),
            [owner_filter, closed_filter]
        )
        self.assertEqual(1, len([x for x in doc_generator]))

    def test_group_filters(self):
        group_filter = GroupOwnerFilter(self.group_id)
        doc_generator = get_export_documents(
            CaseExportInstance(domain=DOMAIN, case_type=DEFAULT_CASE_TYPE),
            [group_filter]
        )
        self.assertEqual(2, len([x for x in doc_generator]))

    def test_get_case_export_base_query(self):
        q = get_case_export_base_query(DOMAIN, DEFAULT_CASE_TYPE)
        result = q.run()
        self.assertEqual(4, len(result.hits))

    def test_form_submitted_by_none_filter(self):
        """
        Confirm that the FormSubmittedByFilter works when None is one of the
        arguments.
        """
        doc_generator = get_export_documents(
            FormExportInstance(domain=DOMAIN, app_id=DEFAULT_APP_ID, xmlns=DEFAULT_XMLNS),
            [FormSubmittedByFilter([uuid.uuid4().hex, None, uuid.uuid4().hex])]
        )
        self.assertEqual(1, len([x for x in doc_generator]))
