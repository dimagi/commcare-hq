import json
import os
from couchdbkit import ResourceNotFound, ResourceConflict
import datetime
from django.test.testcases import TestCase
from casexml.apps.case.models import CommCareCase
from corehq.apps.indicators.models import (
    FormLabelIndicatorDefinition,
    FormDataInCaseIndicatorDefinition,
    FormDataAliasIndicatorDefinition,
)
from mvp_docs.models import IndicatorXForm, IndicatorCase
from mvp_docs.pillows import MVPFormIndicatorPillow, MVPCaseIndicatorPillow
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db

INDICATOR_TEST_DOMAIN = 'indicator-domain'
INDICATOR_TEST_NAMESPACE = 'indicator_test'


class IndicatorPillowTests(TestCase):

    def setUp(self):
        try:
            get_db().delete_doc('INDICATOR_CONFIGURATION')
        except ResourceNotFound:
            pass
        get_db().save_doc({
            '_id': 'INDICATOR_CONFIGURATION',
            'namespaces': {
                INDICATOR_TEST_DOMAIN: [
                    [
                        INDICATOR_TEST_NAMESPACE,
                        "INDICATOR TEST Namespace",
                    ],
                ],
            }
        })
        self.form_pillow = MVPFormIndicatorPillow()
        self.case_pillow = MVPCaseIndicatorPillow()

    def _get_doc_data(self, docname):
        file_path = os.path.join(os.path.dirname(__file__), "data", docname)
        with open(file_path, "rb") as f:
            return json.loads(f.read())

    def _save_doc_to_db(self, docname, doc_class):
        doc_dict = self._get_doc_data(docname)
        try:
            doc_instance = doc_class.wrap(doc_dict)
            doc_instance.save()
        except ResourceConflict:
            doc_instance = doc_class.get(doc_dict['_id'])
            doc_instance._doc.update(doc_dict)
        return doc_dict['_id']

    def test_form_pillow_indicators(self):
        form_id = self._save_doc_to_db('indicator_form.json', XFormInstance)
        form_instance = XFormInstance.get(form_id)

        # Form Label Indicator
        form_label = FormLabelIndicatorDefinition.increment_or_create_unique(
            INDICATOR_TEST_NAMESPACE,
            INDICATOR_TEST_DOMAIN,
            slug='create_form',
            xmlns='http://openrosa.org/formdesigner/indicator-create-xmlns',
        )
        form_label.save()

        # Form Alias
        form_alias = FormDataAliasIndicatorDefinition.increment_or_create_unique(
            INDICATOR_TEST_NAMESPACE,
            INDICATOR_TEST_DOMAIN,
            slug='club_name',
            question_id='location.club',
            xmlns='http://openrosa.org/formdesigner/indicator-create-xmlns',
        )
        form_alias.save()

        self.form_pillow.run_burst()

        indicator_form = IndicatorXForm.get(form_id)
        self.assertNotEqual(
            indicator_form.get_db().dbname, form_instance.get_db().dbname
        )
        self.assertNotEqual(indicator_form.computed_, {})

    def test_case_pillow_indicators(self):
        self._save_doc_to_db('indicator_form.json', XFormInstance)
        case_id = self._save_doc_to_db('indicator_case.json', CommCareCase)
        case_instance = CommCareCase.get(case_id)

        # FormDataInCaseIndicatorDef (For those forgotten properties)
        forgotten_property = FormDataInCaseIndicatorDefinition.increment_or_create_unique(
            INDICATOR_TEST_NAMESPACE,
            INDICATOR_TEST_DOMAIN,
            slug='club_name',
            question_id='location.club',
            case_type='song_tag',
            xmlns='http://openrosa.org/formdesigner/indicator-create-xmlns',
        )
        forgotten_property.save()

        self.case_pillow.run_burst()

        indicator_case = IndicatorCase.get(case_id)

        self.assertEqual(indicator_case.get_id, case_instance.get_id)
        self.assertNotEqual(
            indicator_case.get_db().dbname, case_instance.get_db().dbname
        )
        self.assertNotEqual(indicator_case.computed_, {})

    def test_delete_doc(self):
        form = IndicatorXForm()
        form.save()
        self.assertTrue(IndicatorXForm.get_db().doc_exist(form._id))
        self.form_pillow.change_transform({'_id': form._id, 'doc_type': 'XFormArchived'})
        self.assertFalse(IndicatorXForm.get_db().doc_exist(form._id))

    def test_delete_doc_that_doesnt_exist(self):
        # this test just makes sure we don't crash in this scenario so there are no assertions
        self.form_pillow.change_transform(
            {'_id': 'some-bad-id', '_rev': 'whatrever', 'doc_type': 'XFormArchived'}
        )
