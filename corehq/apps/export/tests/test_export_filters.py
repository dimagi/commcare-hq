from __future__ import absolute_import
from __future__ import unicode_literals
import uuid

from django.test import SimpleTestCase
from elasticsearch.exceptions import ConnectionError

from corehq.apps.export.esaccessors import get_case_export_base_query
from corehq.apps.export.export import (
    get_export_documents,
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
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO
from corehq.pillows.mappings.group_mapping import GROUP_INDEX_INFO
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup
from pillowtop.es_utils import initialize_index_and_mapping


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
        with trap_extra_setup(ConnectionError, msg="cannot connect to elasicsearch"):
            es = get_es_new()
            cls.tearDownClass()
            initialize_index_and_mapping(es, CASE_INDEX_INFO)
            initialize_index_and_mapping(es, GROUP_INDEX_INFO)
            initialize_index_and_mapping(es, XFORM_INDEX_INFO)

        case = new_case(closed=True)
        send_to_elasticsearch('cases', case.to_json())

        case = new_case(closed=False)
        send_to_elasticsearch('cases', case.to_json())

        case = new_case(closed=True, owner_id="foo")
        send_to_elasticsearch('cases', case.to_json())

        case = new_case(closed=False, owner_id="bar")
        send_to_elasticsearch('cases', case.to_json())

        group = Group(_id=uuid.uuid4().hex, users=["foo", "bar"])
        cls.group_id = group._id
        send_to_elasticsearch('groups', group.to_json())

        form = new_form(form={"meta": {"userID": None}})
        send_to_elasticsearch('forms', form.to_json())

        form = new_form(form={"meta": {"userID": ""}})
        send_to_elasticsearch('forms', form.to_json())

        form = new_form(form={"meta": {"deviceID": "abc"}})
        send_to_elasticsearch('forms', form.to_json())

        form = new_form(form={"meta": {"userID": uuid.uuid4().hex}})
        send_to_elasticsearch('forms', form.to_json())

        es.indices.refresh(CASE_INDEX_INFO.index)
        es.indices.refresh(XFORM_INDEX_INFO.index)
        es.indices.refresh(GROUP_INDEX_INFO.index)

    @classmethod
    def tearDownClass(cls):
        ensure_index_deleted(CASE_INDEX_INFO.index)
        ensure_index_deleted(XFORM_INDEX_INFO.index)
        ensure_index_deleted(GROUP_INDEX_INFO.index)

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
