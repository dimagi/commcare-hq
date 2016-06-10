import uuid
from django.core.urlresolvers import reverse
from urllib import urlencode

from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import normalize_username
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.form_processor.submission_post import SubmissionPost
import django_digest.test
from django.test import TestCase
import os
from corehq.apps.app_manager.models import Application
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.receiverwrapper.views import secure_post


class FakeFile(object):

    def __init__(self, data, name=None):
        self.data = data
        self.name = name

    def read(self):
        return self.data


class _AuthTest(TestCase):

    def setUp(self):
        self._set_up_domain()

        try:
            self.user = CommCareUser.create(
                self.domain,
                username=normalize_username('danny', self.domain),
                password='1234',
            )
        except CommCareUser.Inconsistent:
            pass

        self.app = Application.new_app(self.domain, 'My Crazy App', '2.0')
        self.app.save()

        self.url = reverse(secure_post, args=[self.domain, self.app.get_id])

    @property
    def bare_form(self):
        return os.path.join(
            os.path.dirname(__file__), "data", 'bare_form.xml'
        )

    @property
    def form_with_case(self):
        return os.path.join(
            os.path.dirname(__file__), "data", 'form_with_case.xml'
        )

    @property
    def form_with_demo_case(self):
        return os.path.join(
            os.path.dirname(__file__), "data", 'form_with_demo_case.xml'
        )

    @property
    def device_log(self):
        return os.path.join(
            os.path.dirname(__file__), "data", 'device_log.xml'
        )

    def tearDown(self):
        self.user.delete()

    def _test_post(self, file_path, authtype=None, client=None,
                   expected_status=201, expected_auth_context=None,
                   submit_mode=None, expected_response=None):
        if not client:
            client = django_digest.test.Client()

        def _make_url():
            url = self.url
            url_params = {}
            if authtype:
                url_params['authtype'] = authtype
            if submit_mode:
                url_params['submit_mode'] = submit_mode
            url = '%s?%s' % (url, urlencode(url_params))
            return url

        url = _make_url()
        with open(file_path, "rb") as f:
            fileobj = FakeFile(
                f.read().format(
                    userID=self.user.user_id,
                    instanceID=uuid.uuid4().hex,
                    case_id=uuid.uuid4().hex,
                ),
                name=file_path,
            )
            response = client.post(url, {"xml_submission_file": fileobj})
        self.assertEqual(response.status_code, expected_status)

        if expected_response:
            self.assertEqual(response.content, expected_response)

        if expected_auth_context is not None:
            xform_id = response['X-CommCareHQ-FormID']
            xform = FormAccessors(self.domain).get_form(xform_id)
            self.assertEqual(xform.auth_context, expected_auth_context)
            return xform

    @run_with_all_backends
    def test_digest(self):
        client = django_digest.test.Client()
        client.set_authorization(self.user.username, '1234',
                                 method='Digest')
        expected_auth_context = {
            'doc_type': 'AuthContext',
            'domain': self.domain,
            'authenticated': True,
            'user_id': self.user.get_id,
        }
        self._test_post(
            file_path=self.bare_form,
            client=client,
            expected_auth_context=expected_auth_context,
            authtype='digest',
        )

    def test_submit_mode(self):
        # test 'submit_mode=demo' request param

        accepted_response = SubmissionPost.get_success_response(None, None).content
        ignored_response = SubmissionPost.submission_ignored_response().content

        # submissions with 'submit_mode=demo' param should be ignored
        self._test_post(
            file_path=self.bare_form,
            authtype='noauth',
            submit_mode='demo',
            expected_response=ignored_response
        )
        # submissions with 'submit_mode=demo' param by real users should be ignored
        client = django_digest.test.Client()
        client.set_authorization(self.user.username, '1234',
                                 method='Digest')
        self._test_post(
            file_path=self.bare_form,
            client=client,
            authtype='digest',
            submit_mode='demo',
            expected_response=ignored_response
        )

        # submissions by 'demo_user' should not be ignored even with 'submit_mode=demo' param
        self._test_post(
            file_path=self.form_with_demo_case,
            authtype='noauth',
            submit_mode='demo',
            expected_response=accepted_response
        )

    @run_with_all_backends
    def test_basic(self):
        client = django_digest.test.Client()
        client.set_authorization(self.user.username, '1234',
                                 method='Basic')
        expected_auth_context = {
            'doc_type': 'AuthContext',
            'domain': self.domain,
            'authenticated': True,
            'user_id': self.user.get_id,
        }
        self._test_post(
            file_path=self.bare_form,
            client=client,
            authtype='basic',
            expected_status=201,
            expected_auth_context=expected_auth_context
        )
        # by default, ?authtype=basic should be equivalent to having no authtype
        self._test_post(
            file_path=self.bare_form,
            client=client,
            expected_status=201,
            expected_auth_context=expected_auth_context
        )

    @run_with_all_backends
    def test_noauth_nometa(self):
        self._test_post(
            file_path=self.bare_form,
            authtype='noauth',
            expected_status=403,
        )

    @run_with_all_backends
    def test_noauth_devicelog(self):
        self._test_post(
            file_path=self.device_log,
            authtype='noauth',
            expected_status=201,
        )

    @run_with_all_backends
    def test_bad_noauth(self):
        """
        if someone submits a form in noauth mode, but it creates or updates
        cases not owned by demo_user, the form must be rejected
        """

        self._test_post(
            file_path=self.form_with_case,
            authtype='noauth',
            expected_status=403,
        )

    @run_with_all_backends
    def test_case_noauth(self):
        self._test_post(
            file_path=self.form_with_demo_case,
            authtype='noauth',
            expected_status=201,
            expected_auth_context={
                'doc_type': 'WaivedAuthContext',
                'domain': self.domain,
                'authenticated': False,
                'user_id': None,
            }
        )


class AuthTest(_AuthTest):

    domain = 'my-crazy-domain'

    def _set_up_domain(self):
        project = create_domain(self.domain)
        project.secure_submissions = True
        project.save()


class InsecureAuthTest(_AuthTest):

    domain = 'my-crazy-insecure-domain'

    def _set_up_domain(self):
        project = create_domain(self.domain)
        project.secure_submissions = False
        project.save()
