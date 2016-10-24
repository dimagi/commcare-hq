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


def get_diff_filename(filename):
    return "{}.diff.txt".format(filename)


def get_diff(file_v1, file_v2):
    with open(file_v1, "r") as fv1:
        with open(file_v2, "r") as fv2:
            data_v1 = fv1.readlines()
            data_v2 = fv2.readlines()
            differ = difflib.Differ()
            return list(differ.compare(data_v1, data_v2))


class Command(BaseCommand):
    help = '''
    Computes diffs of
    '''

    def handle(self, *args, **options):
        base_dir = os.path.dirname(os.path.realpath(__file__))

        yaml_v1_dir = os.path.join(base_dir, RELATIVE_YAML_V1)
        yaml_v2_dir = os.path.join(base_dir, RELATIVE_YAML_V2)
        yaml_diff_dir = os.path.join(base_dir, RELATIVE_DIFF_STORAGE_YAML)

        common_yaml = filecmp.dircmp(yaml_v1_dir, yaml_v2_dir).common_files

        print("Computing YAML diffs...")
        for yaml_file in common_yaml:
            yaml_file_v1 = os.path.join(yaml_v1_dir, yaml_file)
            yaml_file_v2 = os.path.join(yaml_v2_dir, yaml_file)
            diff_file = os.path.join(yaml_diff_dir, get_diff_filename(yaml_file))
            print(" >> Computing diff for {}".format(yaml_file))
            with open(diff_file, "w") as df:
                df.writelines(get_diff(yaml_file_v1, yaml_file_v2))
