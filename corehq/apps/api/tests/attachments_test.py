import json
import uuid

from datetime import datetime
from io import BytesIO, FileIO, StringIO

from django.http import Http404
from django.test import Client
from django.urls import reverse
from django_otp.tests import TestCase
from mock import patch
from tastypie.models import ApiKey

from corehq.apps.api.object_fetch_api import CaseAttachmentAPI
from corehq.apps.api.tests.utils import mock_image, CachedImageMock

from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.exceptions import AttachmentNotFound
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.interfaces.processor import ProcessedForms
from corehq.form_processor.models import CaseAttachmentSQL, CommCareCaseSQL, XFormInstanceSQL, CaseTransaction, \
    Attachment
from corehq.form_processor.tests.utils import use_sql_backend
from dimagi.utils.django.cached_object import CachedImage


@use_sql_backend
class AttachmentAPITest(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.username = 'garry'
        cls.user_password = 'coleman'
        cls.domain_name = 'attachment-domain'
        cls.attachment_name = 'image.jpg'
        super(AttachmentAPITest, cls).setUpClass()
        cls.domain = Domain.get_or_create_with_name(cls.domain_name, is_active=True)
        cls.domain.save()
        cls._add_test_webuser()

        cls.api_key, _ = ApiKey.objects.get_or_create(user=WebUser.get_django_user(cls.user))
        cls._add_test_case()
        cls._set_client()
        cls.attachment_api = CaseAttachmentAPI()

    @classmethod
    def tearDownClass(cls):
        cls.api_key.delete()
        cls.user.delete()
        cls.attachment.delete()
        cls.case.delete()
        cls.domain.delete()

        super(AttachmentAPITest, cls).tearDownClass()

    @classmethod
    def _add_test_case(cls):
        now = datetime.utcnow()
        form = XFormInstanceSQL(
            form_id='f0rm_id',
            xmlns='http://openrosa.org/formdesigner/form-processor',
            user_id=cls.user.user_id,
            received_on=now,
            domain=cls.domain_name
        )
        case = CommCareCaseSQL(
            case_id='c4se_id',
            domain=cls.domain_name,
            type='',
            owner_id=cls.user.user_id,
            opened_on=now,
            modified_on=now,
            modified_by=cls.user.user_id,
            server_modified_on=now,
            closed=False
        )
        case.track_create(CaseTransaction.form_transaction(case, form, datetime.utcnow()))
        FormProcessorSQL.save_processed_models(ProcessedForms(form, None), [case])

        cls.form = form
        cls.case = CaseAccessorSQL.get_case('c4se_id')
        cls.attachment = CaseAttachmentSQL(
            case=cls.case,
            attachment_id=uuid.uuid4().hex,
            name='image.jpg',
            content_type='image/jpeg',
            blob_id='122',
            md5='123',
        )

        cls.case.track_create(cls.attachment)
        CaseAccessorSQL.save_case(cls.case)

    @classmethod
    def _add_test_webuser(cls):
        cls.user = WebUser.create(cls.domain.name, cls.username, cls.user_password)
        cls.user.set_role(cls.domain.name, 'admin')
        cls.user.save()

    @classmethod
    def _set_client(cls):
        cls.client = Client()

    @classmethod
    def _get_url(cls, type='case'):
        kwargs = {
            "domain": cls.domain.name,
            "attachment_id": "image.jpg",
        }
        if type == 'form':
            kwargs['form_id'] = cls.form.form_id
            return reverse('api_form_attachment', kwargs=kwargs)
        if type == 'case':
            kwargs['case_id'] = cls.case.case_id
            return reverse('api_case_attachment', kwargs=kwargs)

    def image_request_data(self, **kwargs):
        data = {
            'img': 'image.jpg',
            'max_image_width': 10000000,
            'max_image_height': 10000000,
            'max_filesize': 10000000,
            'username': self.username,
            'api_key': self.api_key.key,
        }
        if kwargs:
            data.update(kwargs)
        return data

    @patch.object(CaseAttachmentSQL, 'open', return_value=BytesIO(mock_image().tobytes()))
    @patch('corehq.apps.api.object_fetch_api.get_cached_case_attachment', return_value=CachedImageMock())
    def test_get_attachment_debug(self, object_getter, _):
        with patch.object(CachedImage, "is_cached", return_value=False), \
                patch.object(CachedImage, "cache_put", return_value=None):
            result = self.client.get(self._get_url(), self.image_request_data(size='debug_all'))

        self.assertEqual(result.status_code, 200)
        self.assertIn(
            'src="/a/attachment-domain/api/case/attachment/c4se_id/image.jpg',
            result.content.decode('UTF-8')
        )
        object_getter.assert_called_with(
            self.domain_name, self.case.case_id, self.attachment.name, is_image=True
        )

    @patch.object(CaseAttachmentSQL, 'open', return_value=BytesIO(mock_image().tobytes()))
    @patch('corehq.apps.api.object_fetch_api.get_cached_case_attachment', return_value=CachedImageMock())
    def test_get_attachment(self, object_getter, _):
        with patch.object(CachedImage, "is_cached", return_value=False), \
                patch.object(CachedImage, "cache_put", return_value=None):
            result = self.client.get(self._get_url(), self.image_request_data())

        self.assertEqual(result.status_code, 200)

        object_getter.assert_called_with(
            self.domain_name, self.case.case_id, self.attachment.name, is_image=True)

    @patch.object(CaseAttachmentSQL, 'open', return_value=BytesIO(mock_image().tobytes()))
    @patch('corehq.apps.api.object_fetch_api.get_cached_case_attachment', return_value=CachedImageMock())
    def test_get_attachment_no_constrains(self, object_getter, _):
        with patch.object(CachedImage, "is_cached", return_value=False), \
                patch.object(CachedImage, "cache_put", return_value=None):
            constrains = self.image_request_data()
            constrains['max_image_width'] = 10
            result = self.client.get(self._get_url(), constrains)

        self.assertEqual(result.status_code, 200)

        object_getter.assert_called_with(
            self.domain_name, self.case.case_id, self.attachment.name, is_image=True
        )

    def test_get_attachment_no_attachment_exception(self):
        with patch.object(CachedImage, "is_cached", return_value=False), \
                patch.object(CachedImage, "cache_put", return_value=None):
            with self.assertRaises(AttachmentNotFound):
                self.client.get(self._get_url(), self.image_request_data())

    @patch.object(FormAccessors, 'get_attachment_content', return_value=CachedImageMock())
    def test_get_form_attachment(self, image):
        result = self.client.get(self._get_url(type='form'), self.image_request_data(size='debug_all'))
        actual = next(result.streaming_content)

        self.assertEqual(result.status_code, 200)
        self.assertIsInstance(actual, bytes)

        image.assert_called_with(self.form.form_id, self.attachment.name)

    def test_get_attachment_insufficient_data(self):
        url = reverse('api_form_attachment',
                      kwargs={'domain': self.domain_name, 'form_id': None, 'attachment_id': None})
        result = self.client.get(url, self.image_request_data())
        self.assertEqual(result.status_code, 404)

