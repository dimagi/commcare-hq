from __future__ import print_function
import logging
import os
import filecmp
import difflib

import re
from django.core.management import BaseCommand


logger = logging.getLogger('app_migration')
logger.setLevel('DEBUG')

VERSIONED_DIRS = [
    # List of report builder v1 directories.
    # Paths are relative to corehq/apps/userreports
    "v1/",
    "reports/builder/v1/",
    "static/userreports/js/v1/",
    "templates/userreports/v1/",
    "templates/userreports/partials/v1/",
    "templates/userreports/reportbuilder/v1/",
]

RELATIVE_DIFF_STORAGE = 'tests/data/report_builder_v2_diffs/'



def get_diff_filename(v2_dir, filename):
    dir_part = ".".join([x for x in v2_dir.split("/") if x and x != ".."])
    if dir_part:
        filename = "{}.{}".format(dir_part, filename)
    return "{}.diff.txt".format(filename)


def get_diff(file_v1, file_v2):
    with open(file_v1, "r") as fv1:
        with open(file_v2, "r") as fv2:
            data_v1 = fv1.readlines()
            data_v2 = fv2.readlines()
            return list(difflib.unified_diff(data_v1, data_v2))


class Command(BaseCommand):

    def handle(self, **options):
        self.base_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../..")

        self._make_diffs(
            VERSIONED_DIRS,
            RELATIVE_DIFF_STORAGE,
        )

    def _make_diffs(self, versioned_dirs, rel_diff):

        diff_dir = os.path.join(self.base_dir, rel_diff)

        common_files = []
        for dir in versioned_dirs:
            v1_full = os.path.join(self.base_dir, dir)
            v2_relative = re.sub("v1/$", "", dir)
            v2_full = os.path.join(self.base_dir, v2_relative)

            common_files.extend([
                (dir, v2_relative, f) for f in filecmp.dircmp(v1_full, v2_full).common_files
                if not f.endswith(".pyc")
            ])


        print("Computing diffs...")
        for v1_dir, v2_dir, tracked_file in common_files:
            file_v1 = os.path.join(self.base_dir, v1_dir, tracked_file)
            file_v2 = os.path.join(self.base_dir, v2_dir, tracked_file)
            diff_file = os.path.join(
                diff_dir, get_diff_filename(v2_dir, tracked_file)
            )
            print(" >> Computing diff for {}".format(tracked_file))
            with open(diff_file, "w") as df:
                df.writelines(get_diff(file_v1, file_v2))
