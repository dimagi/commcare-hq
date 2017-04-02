# coding: utf-8
import filecmp
import os
from corehq.apps.app_manager.management.commands.build_app_manager_v2_diffs import (
    get_diff_filename,
    get_diff,
)

from django.test import SimpleTestCase

RELATIVE_DIFF_STORAGE_YAML = 'data/v2_diffs/yaml'
RELATIVE_YAML_V1 = '../static/app_manager/json/v1'
RELATIVE_YAML_V2 = '../static/app_manager/json/v2'

RELATIVE_DIFF_STORAGE_TEMPLATES = 'data/v2_diffs/templates'
RELATIVE_TEMPLATES_V1 = '../templates/app_manager/v1'
RELATIVE_TEMPLATES_V2 = '../templates/app_manager/v2'

RELATIVE_DIFF_STORAGE_PARTIALS = 'data/v2_diffs/partials'
RELATIVE_PARTIALS_V1 = '../templates/app_manager/v1/partials'
RELATIVE_PARTIALS_V2 = '../templates/app_manager/v2/partials'

CREATION_FAILURE_MSG = """


****************************************

Are you editing APP MANAGER V2?

You probably forgot to run ./manage.py build_app_manager_v2_diffs

****************************************



"""

DIFF_FAILURE_MSG = """


*************************************

APP MANAGER V2 Diff Failure

An edit made to a V1 App Manager file "{}" does not match the stored diff
of its V2 counterpart.

**Please make the edits to the V2 file so that it gets the changes from V1.**

Once you have done this, run ./manage.py build_app_manager_v2_diffs
to rebuild the broken diffs.

If the changes are so far off that this process is confusing, please chat with
Biyeun or Jenny. Apologies in advance, if that is the case.

These files are located in
{}
{}

**************************************



"""


class TestAppManagerV2Diffs(SimpleTestCase):

    def setUp(self):
        base_dir = os.path.dirname(os.path.realpath(__file__))

        self.yaml_v1_dir = os.path.join(base_dir, RELATIVE_YAML_V1)
        self.yaml_v2_dir = os.path.join(base_dir, RELATIVE_YAML_V2)
        self.yaml_diff_dir = os.path.join(base_dir, RELATIVE_DIFF_STORAGE_YAML)
        self.common_yaml = filecmp.dircmp(
            self.yaml_v1_dir, self.yaml_v2_dir).common_files

        self.template_v1_dir = os.path.join(base_dir, RELATIVE_TEMPLATES_V1)
        self.template_v2_dir = os.path.join(base_dir, RELATIVE_TEMPLATES_V2)
        self.template_diff_dir = os.path.join(base_dir, RELATIVE_DIFF_STORAGE_TEMPLATES)
        self.common_templates = filecmp.dircmp(
            self.template_v1_dir, self.template_v2_dir).common_files

        self.partial_v1_dir = os.path.join(base_dir, RELATIVE_PARTIALS_V1)
        self.partial_v2_dir = os.path.join(base_dir, RELATIVE_PARTIALS_V2)
        self.partial_diff_dir = os.path.join(base_dir, RELATIVE_DIFF_STORAGE_PARTIALS)
        self.common_partials = filecmp.dircmp(
            self.partial_v1_dir, self.partial_v2_dir).common_files

    def _test_exist_util(self, common_files, diff_dir):
        for test_file in common_files:
            self.assertTrue(
                os.path.exists(os.path.join(
                    diff_dir,
                    get_diff_filename(test_file)
                )), CREATION_FAILURE_MSG
            )

    def _test_diffs_util(self, common_files, diff_dir, v1_dir, v2_dir):
        for test_file in common_files:
            diff_filename = os.path.join(
                diff_dir,
                get_diff_filename(test_file)
            )
            filename_v1 = os.path.join(v1_dir, test_file)
            filename_v2 = os.path.join(v2_dir, test_file)
            try:
                with open(diff_filename, 'r') as diff_file:
                    existing_diff_lines = diff_file.readlines()
                    current_diff = get_diff(filename_v1, filename_v2)
                    self.assertEqual(
                        "".join(existing_diff_lines),
                        "".join(current_diff),
                        DIFF_FAILURE_MSG.format(
                            test_file, filename_v1, filename_v2
                        )
                    )
            except IOError:
                raise Exception(
                    "Issue opening diff file. "
                    "You may need to manually create it using ./manage.py build_app_manager_v2_diffs.\n"
                    "File path is {}".format(diff_filename)
                )

    def test_yaml_01_diffs_exist(self):
        """
        Tests that diff files exists for the split V1/V2 YAML Files
        """
        self._test_exist_util(self.common_yaml, self.yaml_diff_dir)

    def test_yaml_02_diffs_match(self):
        """
        Tests that the diffs of the yaml files match what we have
        """
        self._test_diffs_util(
            self.common_yaml,
            self.yaml_diff_dir,
            self.yaml_v1_dir,
            self.yaml_v2_dir
        )

    def test_template_01_diffs_exist(self):
        """
        Tests that diff files exists for the split V1/V2 TEMPLATE Files
        """
        self._test_exist_util(self.common_templates, self.template_diff_dir)

    def test_template_02_diffs_match(self):
        """
        Tests that the diffs of the template files match what we have
        """
        self._test_diffs_util(
            self.common_templates,
            self.template_diff_dir,
            self.template_v1_dir,
            self.template_v2_dir
        )

    def test_partial_01_diffs_exist(self):
        """
        Tests that diff files exists for the split V1/V2 TEMPLATE Files
        """
        self._test_exist_util(self.common_templates, self.template_diff_dir)

    def test_partial_02_diffs_match(self):
        """
        Tests that the diffs of the template files match what we have
        """
        self._test_diffs_util(
            self.common_partials,
            self.partial_diff_dir,
            self.partial_v1_dir,
            self.partial_v2_dir
        )
