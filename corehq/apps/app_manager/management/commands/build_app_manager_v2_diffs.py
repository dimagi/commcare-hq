from __future__ import print_function
import logging
import os
import filecmp
import difflib

from django.core.management import BaseCommand


logger = logging.getLogger('app_migration')
logger.setLevel('DEBUG')

RELATIVE_YAML_V1 = '../../static/app_manager/json/v1'
RELATIVE_YAML_V2 = '../../static/app_manager/json/v2'
RELATIVE_DIFF_STORAGE_YAML = '../../tests/data/v2_diffs/yaml'

RELATIVE_TEMPLATE_V1 = '../../templates/app_manager/v1'
RELATIVE_TEMPLATE_V2 = '../../templates/app_manager/v2'
RELATIVE_DIFF_STORAGE_TEMPLATES = '../../tests/data/v2_diffs/templates'

RELATIVE_PARTIALS_V1 = '../../templates/app_manager/v1/partials'
RELATIVE_PARTIALS_V2 = '../../templates/app_manager/v2/partials'
RELATIVE_DIFF_STORAGE_PARTIALS = '../../tests/data/v2_diffs/partials'


def get_diff_filename(filename):
    return "{}.diff.txt".format(filename)


def get_diff(file_v1, file_v2):
    with open(file_v1, "r") as fv1:
        with open(file_v2, "r") as fv2:
            data_v1 = fv1.readlines()
            data_v2 = fv2.readlines()
            return list(difflib.unified_diff(data_v1, data_v2))


class Command(BaseCommand):
    help = '''
    Computes diffs of
    '''

    def handle(self, **options):
        self.base_dir = os.path.dirname(os.path.realpath(__file__))
        self._make_diffs(
            RELATIVE_YAML_V1,
            RELATIVE_YAML_V2,
            RELATIVE_DIFF_STORAGE_YAML,
            "YAML"
        )
        self._make_diffs(
            RELATIVE_TEMPLATE_V1,
            RELATIVE_TEMPLATE_V2,
            RELATIVE_DIFF_STORAGE_TEMPLATES,
            "TEMPLATE"
        )
        self._make_diffs(
            RELATIVE_PARTIALS_V1,
            RELATIVE_PARTIALS_V2,
            RELATIVE_DIFF_STORAGE_PARTIALS,
            "PARTIAL"
        )

    def _make_diffs(self, rel_v1, rel_v2, rel_diff, type_name):
        v1_dir = os.path.join(self.base_dir, rel_v1)
        v2_dir = os.path.join(self.base_dir, rel_v2)
        diff_dir = os.path.join(self.base_dir, rel_diff)

        common = filecmp.dircmp(v1_dir, v2_dir).common_files

        print("Computing {} diffs...".format(type_name))
        for tracked_file in common:
            file_v1 = os.path.join(v1_dir, tracked_file)
            file_v2 = os.path.join(v2_dir, tracked_file)
            diff_file = os.path.join(diff_dir,
                                     get_diff_filename(tracked_file))
            print(" >> Computing diff for {}".format(tracked_file))
            with open(diff_file, "w") as df:
                df.writelines(get_diff(file_v1, file_v2))
