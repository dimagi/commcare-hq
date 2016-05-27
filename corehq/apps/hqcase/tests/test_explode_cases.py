import datetime
import uuid
from contextlib import contextmanager

from couchdbkit import ResourceNotFound
from django.test import SimpleTestCase, TestCase
from mock import patch

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.sharedmodels import CommCareCaseAttachment
from casexml.apps.case.tests.util import delete_all_cases, delete_all_xforms
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.hqcase.tasks import explode_cases
from corehq.apps.hqcase.utils import make_creating_casexml, submit_case_blocks
from corehq.apps.users.models import CommCareUser
from corehq.apps.domain.models import Domain
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import run_with_all_backends


TESTS = (
    (
        CommCareCase(
            _id='case-abc123',
            domain='foo',
            type='my_case',
            closed=False,
            user_id='user-abc123',
            modified_on=datetime.datetime(2011, 12, 20, 0, 11, 2),
            owner_id='group-abc123',
            name='Jessica',
            version='2.0',
            indices=[],
            case_attachments={
                'fruity_file': CommCareCaseAttachment(
                    attachment_from=u'local',
                    attachment_name=None,
                    attachment_properties={'width': 240, 'height': 164},
                    attachment_size=22731,
                    attachment_src=u'./corehq/ex-submodules/casexml/apps/case/tests/data/attachments/fruity.jpg',
                    doc_type=u'CommCareCaseAttachment',
                    identifier=u'fruity_file',
                    server_md5=None,
                    server_mime=u'image/jpeg',
                )
            },

            age='25',
        ),
        {u'fruity_file': u'./corehq/ex-submodules/casexml/apps/case/tests/data/attachments/fruity.jpg'},
        """
        <case case_id="new-case-abc123" date_modified="2011-12-20T00:11:02.000000Z"
                user_id="user-abc123"
                xmlns="http://commcarehq.org/case/transaction/v2">
            <create>
                <case_type>my_case</case_type>
                <case_name>Jessica</case_name>
                <owner_id>group-abc123</owner_id>
            </create>
            <update>
                <age>25</age>
            </update>
            <attachment>
                <fruity_file from="local" src="./corehq/ex-submodules/casexml/apps/case/tests/data/attachments/fruity.jpg"/>
            </attachment>
        </case>
        """
    ),
)


@contextmanager
def mock_fetch_case_attachment(case_id, attachments):

    class MockCachedObject(object):

        def __init__(self, attachment_file):
            self.attachment_file = attachment_file

        def get(self, **kwargs):
            return None, open(self.attachment_file)

    def get_cached_case_attachment(domain, _case_id, attachment_id):
        if case_id == _case_id and attachment_id in attachments:
            return MockCachedObject(attachments[attachment_id])
        else:
            raise ResourceNotFound()

    with patch('corehq.apps.hqcase.utils.get_cached_case_attachment', get_cached_case_attachment):
        yield


class ExplodeCasesTest(SimpleTestCase, TestXmlMixin):
    maxDiff = 1000000

    def test_make_creating_casexml(self):
        for input, files, output in TESTS:
            with mock_fetch_case_attachment(input.case_id, files):
                case_block, attachments = make_creating_casexml(
                    'mock-domain', input, 'new-case-abc123')
                self.assertXmlEqual(case_block, output)
                self.assertDictEqual(
                    {key: value.read() for key, value in attachments.items()},
                    {value: open(value).read() for key, value in files.items()}
                )


class ExplodeCasesDbTest(TestCase):

    @classmethod
    def setUpClass(cls):
        delete_all_cases()
        cls.domain = Domain(name='foo')
        cls.domain.save()
        cls.user = CommCareUser.create(cls.domain.name, 'somebody', 'password')
        cls.user_id = cls.user._id

    def setUp(self):
        self.accessor = CaseAccessors(self.domain.name)
        delete_all_cases()
        delete_all_xforms()

    def tearDown(self):
        delete_all_cases()
        delete_all_xforms()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.domain.delete()

    @run_with_all_backends
    def test_simple(self):
        caseblock = CaseBlock(
            create=True,
            case_id=uuid.uuid4().hex,
            user_id=self.user_id,
            owner_id=self.user_id,
            case_type='exploder-type',
        ).as_string()
        submit_case_blocks([caseblock], self.domain.name)
        self.assertEqual(1, len(self.accessor.get_case_ids_in_domain()))
        explode_cases(self.user_id, self.domain.name, 10)

        case_ids = self.accessor.get_case_ids_in_domain()
        cases_back = list(self.accessor.iter_cases(case_ids))
        self.assertEqual(10, len(cases_back))
        for case in cases_back:
            self.assertEqual(self.user_id, case.owner_id)

    @run_with_all_backends
    def test_skip_user_case(self):
        caseblock = CaseBlock(
            create=True,
            case_id=uuid.uuid4().hex,
            user_id=self.user_id,
            owner_id=self.user_id,
            case_type='commcare-user',
        ).as_string()
        submit_case_blocks([caseblock], self.domain.name)
        self.assertEqual(1, len(self.accessor.get_case_ids_in_domain()))
        explode_cases(self.user_id, self.domain.name, 10)

        case_ids = self.accessor.get_case_ids_in_domain()
        cases_back = list(self.accessor.iter_cases(case_ids))
        self.assertEqual(1, len(cases_back))
        for case in cases_back:
            self.assertEqual(self.user_id, case.owner_id)

    @run_with_all_backends
    def test_parent_child(self):
        parent_id = uuid.uuid4().hex
        parent_type = 'exploder-parent-type'
        parent_block = CaseBlock(
            create=True,
            case_id=parent_id,
            user_id=self.user_id,
            owner_id=self.user_id,
            case_type=parent_type,
        ).as_string()

        child_id = uuid.uuid4().hex
        child_block = CaseBlock(
            create=True,
            case_id=child_id,
            user_id=self.user_id,
            owner_id=self.user_id,
            case_type='exploder-child-type',
            index={'parent': (parent_type, parent_id)},
        ).as_string()

        submit_case_blocks([parent_block, child_block], self.domain.name)
        self.assertEqual(2, len(self.accessor.get_case_ids_in_domain()))

        explode_cases(self.user_id, self.domain.name, 5)
        case_ids = self.accessor.get_case_ids_in_domain()
        cases_back = list(self.accessor.iter_cases(case_ids))
        self.assertEqual(10, len(cases_back))
        parent_cases = {p.case_id: p for p in filter(lambda case: case.type == parent_type, cases_back)}
        self.assertEqual(5, len(parent_cases))
        child_cases = filter(lambda case: case.type == 'exploder-child-type', cases_back)
        self.assertEqual(5, len(child_cases))
        child_indices = [child.indices[0].referenced_id for child in child_cases]
        # make sure they're different
        self.assertEqual(len(child_cases), len(set(child_indices)))
        for child in child_cases:
            self.assertEqual(1, len(child.indices))
            self.assertTrue(child.indices[0].referenced_id in parent_cases)
