from unittest import skip
from django.test import SimpleTestCase, TestCase


class ExtCaseSuiteXmlTest(SimpleTestCase):

    @skip
    def test_new_ext_case(self):
        """
        Creating a new extension case should add a <datum> to the form's <entry> node
        """


class ExtCaseDeleteTest(TestCase):

    @skip
    def test_ext_case_cascade_close(self):
        """
        An extension case should be closed when its host case is closed
        """


class ExtCasePropertiesTests(SimpleTestCase):

    @skip
    def test_ext_case_read_host_properties(self):
        """
        Properties of a host case should be available in a extension case
        """

    @skip
    def test_host_case_read_ext_properties(self):
        """
        Properties of a extension case should be available in a host case
        """

    @skip
    def test_ext_case_write_host_properties(self):
        """
        A extension case should be available to save host case properties
        """

    @skip
    def test_host_case_write_ext_properties(self):
        """
        A host case should be available to save extension case properties
        """


class ExtCaseCaseXmlTests(SimpleTestCase):

    @skip
    def test_ext_case_sets_relationship(self):
        """
        Adding an extension case should set index relationship to "extension"
        """


class ExtCasesFormActionTests(SimpleTestCase):

    @skip
    def test_form_actions_incl_ext_cases(self):
        """
        ext_cases form action should open extension cases
        """

    @skip
    def test_form_get_ext_case_types(self):
        """
        form.get_ext_case_types should return ext case types
        """

    @skip
    def test_module_get_ext_case_types(self):
        """
        module.get_ext_case_types should return ext case types
        """


class ExtCaseAdvancedFormCaseXmlTests(SimpleTestCase):
    pass
