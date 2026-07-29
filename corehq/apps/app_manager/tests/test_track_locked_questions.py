"""Tests for counting the questions a form builder save newly locks,
used for the ``cp_n_questions_locked`` domain metric."""
from unittest.mock import patch

from corehq.apps.app_manager.tests.test_get_questions import AppFormTestCase
from corehq.apps.app_manager.views import forms as forms_views
from corehq.apps.app_manager.views.forms import _count_newly_locked_questions

QUESTION2_LOCKED_BIND = '<bind nodeset="/data/question2" type="xsd:string" vellum:lock="all" />'
QUESTION2_UNLOCKED_BIND = '<bind nodeset="/data/question2" type="xsd:string" />'
QUESTION3_UNLOCKED_BIND = '<bind nodeset="/data/question3" type="xsd:string" />'
QUESTION3_LOCKED_BIND = '<bind nodeset="/data/question3" type="xsd:string" vellum:lock="all" />'
QUESTION16_UNLOCKED_BIND = '<bind nodeset="/data/question15/question16" type="xsd:string" constraint="1" />'
QUESTION16_LOCKED_BIND = (
    '<bind nodeset="/data/question15/question16" type="xsd:string" constraint="1" vellum:lock="all" />'
)


class CountNewlyLockedQuestionsTest(AppFormTestCase):
    """The ``case_in_form`` fixture already locks ``/data/question2``."""

    def setUp(self):
        super().setUp()
        self.form = self.app.get_form(self.add_form('case_in_form', "Form").unique_id)

    def count(self, new_xml, has_privilege=True):
        with patch.object(forms_views, 'domain_has_privilege', return_value=has_privilege):
            return _count_newly_locked_questions(self.domain, self.form, new_xml.encode('utf-8'))

    def modified_source(self, old, new):
        modified = self.form.source.replace(old, new)
        assert modified != self.form.source
        return modified

    def test_newly_locked_bind_is_counted(self):
        new_xml = self.modified_source(QUESTION3_UNLOCKED_BIND, QUESTION3_LOCKED_BIND)
        assert self.count(new_xml) == 1

    def test_multiple_newly_locked_binds_are_counted(self):
        new_xml = self.modified_source(QUESTION3_UNLOCKED_BIND, QUESTION3_LOCKED_BIND)
        new_xml = new_xml.replace(QUESTION16_UNLOCKED_BIND, QUESTION16_LOCKED_BIND)
        assert new_xml != self.form.source
        assert self.count(new_xml) == 2

    def test_newly_locked_data_node_is_counted(self):
        new_xml = self.modified_source('<question3 />', '<question3 vellum:lock="all" />')
        assert self.count(new_xml) == 1

    def test_question_locked_before_and_after_is_not_counted(self):
        assert self.count(self.form.source) == 0

    def test_unlocking_is_not_counted(self):
        new_xml = self.modified_source(QUESTION2_LOCKED_BIND, QUESTION2_UNLOCKED_BIND)
        assert self.count(new_xml) == 0

    def test_zero_without_privilege(self):
        new_xml = self.modified_source(QUESTION3_UNLOCKED_BIND, QUESTION3_LOCKED_BIND)
        assert self.count(new_xml, has_privilege=False) == 0

    def test_zero_for_unparseable_xml(self):
        assert self.count('<data><unclosed>') == 0

    def test_corrupt_stored_source_counts_all_locked(self):
        new_xml = self.modified_source(QUESTION3_UNLOCKED_BIND, QUESTION3_LOCKED_BIND)
        self.form.source = '<data><unclosed>'
        assert self.count(new_xml) == 2

    def test_zero_for_xml_with_entities(self):
        entity_xml = '<!DOCTYPE data [<!ENTITY e "x">]><data>&e;</data>'
        assert self.count(entity_xml) == 0

    def test_stored_source_with_entities_counts_all_locked(self):
        new_xml = self.modified_source(QUESTION3_UNLOCKED_BIND, QUESTION3_LOCKED_BIND)
        self.form.source = '<!DOCTYPE data [<!ENTITY e "x">]><data>&e;</data>'
        assert self.count(new_xml) == 2
