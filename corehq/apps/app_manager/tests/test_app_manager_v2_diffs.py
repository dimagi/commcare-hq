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

CREATION_FAILURE_MSG = """


****************************************

Are you editing APP MANAGER V2?

You probably forgot to run ./manage.py build_app_manager_v2_diffs

****************************************



"""

DIFF_FAILURE_YAML = """


*************************************

APP MANAGER V2 Diff Failure

An edit made to a V1 App Manager YAML file "{}" does not match the stored diff
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

        self.common_yaml = filecmp.dircmp(self.yaml_v1_dir, self.yaml_v2_dir).common_files

    def test_yaml_01_diffs_exist(self):
        """
        Tests that diff files exists for the split V1/V2 YAML Files
        """
        for yaml_file in self.common_yaml:
            self.assertTrue(
                os.path.exists(os.path.join(
                    self.yaml_diff_dir,
                    get_diff_filename(yaml_file)
                )), CREATION_FAILURE_MSG
            )

    def test_yaml_02_diffs_match(self):
        """
        Tests that the diffs of the yaml files match what we have
        """
        for yaml_file in self.common_yaml:
            diff_filename = os.path.join(
                self.yaml_diff_dir,
                get_diff_filename(yaml_file)
            )
            filename_v1 = os.path.join(self.yaml_v1_dir, yaml_file)
            filename_v2 = os.path.join(self.yaml_v2_dir, yaml_file)

            with open(diff_filename, 'r') as diff_file:
                existing_diff_lines = diff_file.readlines()
                current_diff = get_diff(filename_v1, filename_v2)
                self.assertEqual(
                    "".join(existing_diff_lines),
                    "".join(current_diff),
                    DIFF_FAILURE_YAML.format(
                        yaml_file, filename_v1, filename_v2
                    )
                )


