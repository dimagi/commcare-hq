from django.core.management import BaseCommand
from xlrd import open_workbook

from custom.rch.models import AreaMapping


class Command(BaseCommand):
    # ./manage.py create_mdds_awc_mappings '/Users/Manish/Documents/RCH-CAS/MDDSData-WG-2.xls'
    help = "Create MDDS_AWC table from xls sheet"
    args = '<path to xls file>'

    def add_arguments(self, parser):
        parser.add_argument('path_to_file')

    def handle(self, path_to_file, *args, **options):
        sheet = open_workbook(path_to_file).sheets()[0]
        for row in range(1, sheet.nrows):
            new_area_mapping = AreaMapping()
            new_area_mapping.stcode = int(sheet.cell(row, 0).value)
            new_area_mapping.stname = sheet.cell(row, 1).value
            new_area_mapping.dtcode = int(sheet.cell(row, 2).value)
            new_area_mapping.dtname = sheet.cell(row, 3).value
            new_area_mapping.pjcode = int(sheet.cell(row, 4).value)
            new_area_mapping.pjname = sheet.cell(row, 5).value
            new_area_mapping.awcid = int(sheet.cell(row, 6).value)
            new_area_mapping.awcname = sheet.cell(row, 7).value
            new_area_mapping.village_code = int(sheet.cell(row, 8).value)
            new_area_mapping.village_name = sheet.cell(row, 9).value
            new_area_mapping.save()
