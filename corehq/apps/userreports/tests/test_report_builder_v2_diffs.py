# coding: utf-8
import filecmp
import os

import re

from corehq.apps.userreports.management.commands.build_report_builder_v2_diffs import (
    get_diff_filename,
    get_diff,
    VERSIONED_DIRS,
)

from django.test import SimpleTestCase

RELATIVE_DIFF_STORAGE_TEMPLATES = 'data/report_builder_v2_diffs'


CREATION_FAILURE_MSG = """


****************************************

Are you editing REPORT BUILDER V2?

You probably forgot to run ./manage.py build_report_builder_v2_diffs

****************************************



"""

DIFF_FAILURE_MSG = """


*************************************

REPORT BUILDER V2 Diff Failure

An edit made to a V1 Report Builder file "{}" does not match the stored diff
of its V2 counterpart.

**Please make the edits to the V2 file so that it gets the changes from V1.**

Once you have done this, run ./manage.py build_report_builder_v2_diffs
to rebuild the broken diffs.

These files are located in
{}
{}

**************************************



"""


class TestReportBuilderV2Diffs(SimpleTestCase):

    def setUp(self):
        this_dir = os.path.dirname(os.path.realpath(__file__))
        self.diff_dir = os.path.join(this_dir, RELATIVE_DIFF_STORAGE_TEMPLATES)
        self.base_dir = os.path.join(this_dir, "..")
        self.common_files = []
        for dir in VERSIONED_DIRS:
            v1_dir = os.path.join(self.base_dir, dir)
            v2_dir = os.path.join(self.base_dir, re.sub("v1/$", "", dir))
            self.common_files.extend([
                (v1_dir, v2_dir, f) for f in filecmp.dircmp(v1_dir, v2_dir).common_files
                if not f.endswith(".pyc")
            ])

    def test_diffs_exist(self):
        for v1_dir, v2_dir, f in self.common_files:
            self.assertTrue(
                os.path.exists(os.path.join(
                    self.diff_dir,
                    get_diff_filename(v2_dir.replace(self.base_dir, ""), f)
                )), CREATION_FAILURE_MSG
            )

    def test_diffs(self):

        for v1_dir, v2_dir, f in self.common_files:
            v2_dir_relative = v2_dir.replace(self.base_dir, "")
            diff_filename = os.path.join(
                self.diff_dir,
                get_diff_filename(v2_dir_relative, f)
            )
            filename_v1 = os.path.join(v1_dir, f)
            filename_v2 = os.path.join(v2_dir, f)

            try:
                with open(diff_filename, 'r') as diff_file:
                    existing_diff_lines = diff_file.readlines()
                    current_diff = get_diff(filename_v1, filename_v2)
                    self.assertEqual(
                        "".join(existing_diff_lines),
                        "".join(current_diff),
                        DIFF_FAILURE_MSG.format(
                            f, filename_v1, filename_v2
                        )
                    )
            except IOError:
                raise Exception(
                    "Issue opening diff file. "
                    "You may need to manually create it using ./manage.py build_report_builder_v2_diffs.\n"
                    "File path is {}".format(diff_filename)
                )
