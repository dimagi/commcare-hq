import datetime
from couchdbkit import ResourceNotFound
from django.test import SimpleTestCase
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.sharedmodels import CommCareCaseAttachment
from corehq.apps.app_manager.tests import TestFileMixin
from corehq.apps.hqcase.utils import make_creating_casexml


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
        <case case_id="new-case-abc123" date_modified="2011-12-20T00:11:02Z"
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


class mock_fetch_case_attachment(object):
    def __init__(self, case_id, attachments):
        _case_id = case_id

        self.old_db = CommCareCase.get_db()

        @classmethod
        def fetch_case_attachment(cls, case_id, attachment_key, fixed_size=None, **kwargs):
            if case_id == _case_id and attachment_key in attachments:
                return None, open(attachments[attachment_key])
            else:
                raise ResourceNotFound()

        self.old_fetch_case_attachment = CommCareCase.fetch_case_attachment
        self.fetch_case_attachment = fetch_case_attachment

    def __enter__(self):
        CommCareCase.fetch_case_attachment = self.fetch_case_attachment

    def __exit__(self, exc_type, exc_val, exc_tb):
        CommCareCase.fetch_case_attachment = self.old_fetch_case_attachment


class ExplodeCasesTest(SimpleTestCase, TestFileMixin):
    maxDiff = 1000000

    def test_make_creating_casexml(self):
        for input, files, output in TESTS:
            with mock_fetch_case_attachment(input.case_id, files):
                case_block, attachments = make_creating_casexml(
                    input, 'new-case-abc123')
                self.assertXmlEqual(case_block, output)
                self.assertDictEqual(
                    {key: value.read() for key, value in attachments.items()},
                    {value: open(value).read() for key, value in files.items()}
                )
