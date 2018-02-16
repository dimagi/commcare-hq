from __future__ import absolute_import
import json
import os

from couchdbkit import ResourceConflict
from django.test.testcases import TestCase
from mock import patch

from casexml.apps.case.models import CommCareCase
from corehq.apps.indicators.models import (
    FormLabelIndicatorDefinition,
    FormDataInCaseIndicatorDefinition,
    FormDataAliasIndicatorDefinition,
    CaseDataInFormIndicatorDefinition, IndicatorDefinition)
from corehq.apps.indicators.tests.utils import delete_indicator_doc
from corehq.apps.indicators.utils import set_domain_namespace_entry
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from couchforms.models import XFormInstance
from mvp_docs.models import IndicatorXForm, IndicatorCase
from mvp_docs.pillows import (
    get_mvp_form_indicator_pillow, get_mvp_case_indicator_pillow,
    process_indicators_for_case, process_indicators_for_form
)
from pillowtop.feed.couch import change_from_couch_row, get_current_seq

INDICATOR_TEST_DOMAIN = 'indicator-domain'
INDICATOR_TEST_NAMESPACE = 'indicator_test'


class IndicatorPillowTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super(IndicatorPillowTests, cls).setUpClass()
        set_domain_namespace_entry(INDICATOR_TEST_DOMAIN, [
            [INDICATOR_TEST_NAMESPACE, "INDICATOR TEST Namespace"],
        ])
        cls.form_pillow = get_mvp_form_indicator_pillow()
        cls.case_pillow = get_mvp_case_indicator_pillow()

    def setUp(self):
        # memoization across tests can break things
        IndicatorDefinition.get_all.reset_cache()

    @classmethod
    def tearDownClass(cls):
        delete_indicator_doc()
        FormProcessorTestUtils.delete_all_xforms()
        FormProcessorTestUtils.delete_all_cases()
        super(IndicatorPillowTests, cls).tearDownClass()

    def _save_doc_to_db(self, docname, doc_class):
        doc_dict = _get_doc_data(docname)
        try:
            doc_instance = doc_class.wrap(doc_dict)
            doc_instance.save()
        except ResourceConflict:
            doc_instance = doc_class.get(doc_dict['_id'])
            doc_instance._doc.update(doc_dict)
        return doc_dict['_id']

    def test_form_pillow_indicators(self):
        since = get_current_seq(XFormInstance.get_db())
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
        self.form_pillow.process_changes(since=since, forever=False)

        indicator_form = IndicatorXForm.get(form_id)
        self.assertNotEqual(
            indicator_form.get_db().dbname, form_instance.get_db().dbname
        )
        self.assertNotEqual(indicator_form.computed_, {})

    def test_case_pillow_indicators(self):
        since = get_current_seq(XFormInstance.get_db())
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

        self.case_pillow.process_changes(since=since, forever=False)

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
        self.form_pillow.process_change(_change_from_doc({'_id': form._id, 'doc_type': 'XFormArchived'}))
        self.assertFalse(IndicatorXForm.get_db().doc_exist(form._id))

    def test_delete_doc_that_doesnt_exist(self):
        # this test just makes sure we don't crash in this scenario so there are no assertions
        self.form_pillow.process_change(_change_from_doc(
            {'_id': 'some-bad-id', '_rev': 'whatrever', 'doc_type': 'XFormArchived'}
        ))

    def test_mixed_form_and_case_indicators_process_form_then_case(self):
        # this is a regression test for http://manage.dimagi.com/default.asp?165274
        def _test():
            form, case = _save_form_and_case(self)
            process_indicators_for_form(['mvp_indicators'], form.domain, form.to_json())
            updated_form = IndicatorXForm.get(form._id)
            self.addCleanup(updated_form.delete)
            computed = updated_form.computed_['mvp_indicators']
            self.assertEqual(29, len(computed))
            self.assertEqual('child_visit_form', computed['child_visit_form']['value'])
            case_json = _get_doc_data('bug_case.json')
            process_indicators_for_case(['mvp_indicators'], case.domain, case.to_json())
            updated_form = IndicatorXForm.get(form._id)
            updated_computed = updated_form.computed_['mvp_indicators']
            self.assertEqual(29, len(updated_computed))
            self.assertEqual('child_visit_form', updated_computed['child_visit_form']['value'])

        self._call_with_patches(_test)

    def test_mixed_form_and_case_indicators_process_case_then_form(self):
        # this is a regression test for http://manage.dimagi.com/default.asp?165274
        def _test():
            form, case = _save_form_and_case(self)
            process_indicators_for_case(['mvp_indicators'], case.domain, case.to_json())
            updated_form = IndicatorXForm.get(form._id)
            self.addCleanup(updated_form.delete)
            computed = updated_form.computed_['mvp_indicators']
            self.assertEqual(29, len(computed))
            self.assertEqual('child_visit_form', computed['child_visit_form']['value'])

            process_indicators_for_form(['mvp_indicators'], form.domain, form.to_json())
            updated_form = IndicatorXForm.get(form._id)
            updated_computed = updated_form.computed_['mvp_indicators']
            self.assertEqual(29, len(updated_computed))
            self.assertEqual('child_visit_form', updated_computed['child_visit_form']['value'])

        self._call_with_patches(_test)

    @patch('corehq.apps.indicators.utils.get_namespaces')
    @patch('corehq.apps.indicators.models.CaseDataInFormIndicatorDefinition.get_all')
    @patch('corehq.apps.indicators.models.CaseIndicatorDefinition.get_all')
    @patch('corehq.apps.indicators.models.FormIndicatorDefinition.get_all')
    def _call_with_patches(self, fn, form_get_all_patch, case_get_all_patch,
                           case_form_get_all_patch, get_namespaces_patch):
        form_get_all_patch.return_value = _fake_indicators('mvp-sauri-form-indicators.json')
        case_get_all_patch.return_value = _fake_indicators('mvp-sauri-case-indicators.json')
        case_form_get_all_patch.return_value = _fake_indicators('mvp-sauri-case-form-indicators.json')
        get_namespaces_patch.return_value = ['mvp_indicators']
        fn()


def _save_form_and_case(test):
    form = XFormInstance.wrap(_get_doc_data('bug_form.json'))
    form.save()
    test.addCleanup(form.delete)

    case = CommCareCase.wrap(_get_doc_data('bug_case.json'))
    case.save()
    test.addCleanup(case.delete)
    return form, case


def _fake_indicators(filename):
    with open(os.path.join(os.path.dirname(__file__), 'data', filename)) as f:
        indicators = json.loads(f.read())
        return [_wrap(i) for i in indicators]


def _wrap(indicator):
    wrap_classes = {
        'FormLabelIndicatorDefinition': FormLabelIndicatorDefinition,
        'FormDataAliasIndicatorDefinition': FormDataAliasIndicatorDefinition,
        'CaseDataInFormIndicatorDefinition': CaseDataInFormIndicatorDefinition,
        'FormDataInCaseIndicatorDefinition': FormDataInCaseIndicatorDefinition
    }
    return wrap_classes[indicator['doc_type']].wrap(indicator)


def _get_doc_data(docname):
    file_path = os.path.join(os.path.dirname(__file__), "data", docname)
    with open(file_path, "rb") as f:
        return json.loads(f.read())


def _change_from_doc(doc_dict):
    doc_dict['domain'] = INDICATOR_TEST_DOMAIN
    return change_from_couch_row({
        'id': doc_dict['_id'], 'doc': doc_dict
    })
