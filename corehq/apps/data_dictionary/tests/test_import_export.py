import io
import os
import uuid

from bs4 import BeautifulSoup
import openpyxl

from django.test import TestCase
from django.urls import reverse

from corehq.apps.data_dictionary.models import CaseProperty, CasePropertyAllowedValue, CaseType
from corehq.apps.data_dictionary.views import (
    ExportDataDictionaryView, UploadDataDictionaryView, ALLOWED_VALUES_SHEET_SUFFIX)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled, TestFileMixin


@flag_enabled('DATA_DICTIONARY')
class DataDictionaryImportTest(TestCase, TestFileMixin):
    domain_name = uuid.uuid4().hex
    file_path = ('data',)
    root = os.path.dirname(__file__)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain(cls.domain_name)
        cls.couch_user = WebUser.create(None, "test", "foobar", None, None)
        cls.couch_user.add_domain_membership(cls.domain_name, is_admin=True)
        cls.couch_user.save()

    @classmethod
    def tearDownClass(cls):
        cls.couch_user.delete(cls.domain_name, deleted_by=None)
        cls.domain.delete()
        super().tearDownClass()

    def setUp(self):
        self.url = reverse(UploadDataDictionaryView.urlname, args=[self.domain_name])
        self.client.login(username='test', password='foobar')

    def test_clean_import(self):
        fname = self.get_path('clean_data_dictionary', 'xlsx')
        with open(fname, 'rb') as dd_file:
            response = self.client.post(self.url, {'bulk_upload_file': dd_file})
        self.assertEqual(response.status_code, 200)
        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), 'Data dictionary import complete')
        case_types = CaseType.objects.filter(domain=self.domain)
        self.assertEqual(2, case_types.count())
        for i in range(1, 3):
            case_type_name = f'caseType{i}'
            case_type = case_types.get(name=case_type_name)
            self.assertEqual(case_type.properties.count(), 3)
            for data_type in ['plain', 'date', 'select']:
                prop = case_type.properties.get(data_type=data_type, name=f'{data_type}prop')
                if data_type == 'select':
                    vals = ['True', 'False'] if i == 1 else ['Yes', 'No']
                    self.assertEqual(2, prop.allowed_values.count())
                    for val in vals:
                        self.assertEqual(
                            1,
                            prop.allowed_values.filter(
                                allowed_value=val, description=f'{val} description').count())

    def test_broken_import(self):
        fname = self.get_path('broken_data_dictionary', 'xlsx')
        with open(fname, 'rb') as dd_file:
            response = self.client.post(self.url, {'bulk_upload_file': dd_file})
        self.assertEqual(response.status_code, 200)
        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        expected_errors = {
            'Error in valid values for case type caseType1, row 4: missing case property',
            'Error in case type caseType1, row 4: Unable to save valid values longer than 255 characters',
            'Missing valid values sheet for case type caseType2',
            'Error in valid values for case type caseType1, nonexistent property listed (mistake), row(s): 5, 6'
        }
        message_str = str(messages[0])
        soup = BeautifulSoup(message_str)
        received_errors = {elem.text for elem in soup.find_all('li')}
        self.assertEqual(expected_errors, received_errors)


@flag_enabled('DATA_DICTIONARY')
class DataDictionaryExportTest(TestCase):
    domain_name = uuid.uuid4().hex

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain(cls.domain_name)
        cls.couch_user = WebUser.create(None, "test", "foobar", None, None)
        cls.couch_user.add_domain_membership(cls.domain_name, is_admin=True)
        cls.couch_user.save()
        case_types = []
        for i in range(1, 3):
            case_type_obj = CaseType(name=f'caseType{i}', domain=cls.domain_name)
            case_type_obj.save()
            case_types.append(case_type_obj)
            for data_type in ['plain', 'date', 'select']:
                prop = CaseProperty.objects.create(
                    case_type=case_type_obj, name=f'{data_type}prop', data_type=data_type)
                if data_type == 'select':
                    vals = ['True', 'False'] if i == 1 else ['Yes', 'No']
                    for val in vals:
                        CasePropertyAllowedValue.objects.create(
                            case_property=prop, allowed_value=val,
                            description=f'{val} description')
        cls.case_types = case_types

    @classmethod
    def tearDownClass(cls):
        for case_type in cls.case_types:
            case_type.delete()
        cls.couch_user.delete(cls.domain_name, deleted_by=None)
        cls.domain.delete()
        super().tearDownClass()

    def setUp(self):
        self.url = reverse(ExportDataDictionaryView.urlname, args=[self.domain_name])
        self.client.login(username='test', password='foobar')

    def test_export(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['content-type'], 'application/vnd.ms-excel')
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="data_dictionary.xlsx"')
        workbook = openpyxl.load_workbook(io.BytesIO(response.content), read_only=True)
        self.assertEqual(len(workbook.sheetnames), 2 * len(self.case_types))
        for i in range(len(self.case_types)):
            name = self.case_types[i].name
            self.assertEqual(name, workbook.sheetnames[i * 2])
            self.assertEqual(f'{name}{ALLOWED_VALUES_SHEET_SUFFIX}', workbook.sheetnames[i * 2 + 1])
