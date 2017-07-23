from django.core.management import BaseCommand
import csv
from datetime import datetime

from custom.rch.models import RCHRecord, RCH_RECORD_TYPE_MAPPING


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('path_to_file')
        parser.add_argument('beneficiary_type')

    def handle(self, path_to_file, beneficiary_type, *args, **options):
        f = open(path_to_file, 'rU')
        record = {}
        fields = []
        row_num = 0
        for row in csv.reader(f):
            if row_num == 0:
                fields = row
                row_num += 1
            else:
                for field_index in range(0,len(row)):
                    record[fields[field_index]] = row[field_index]


                rch_id_key_field = RCHRecord._get_rch_id_key(beneficiary_type)
                record_pk = record[rch_id_key_field]
                assert record_pk
                results = RCHRecord.objects.filter(rch_id=record_pk)

                if results:
                    rch_beneficiary = results[0]
                    rch_beneficiary.prop_doc['properties'] = record
                else:
                    rch_beneficiary = RCHRecord(doc_type=RCH_RECORD_TYPE_MAPPING[beneficiary_type])

                rch_beneficiary.set_beneficiary_fields(record)
                rch_beneficiary.details = record
                rch_beneficiary.dob = datetime.strptime(rch_beneficiary.dob, "%d/%m/%y")
                if rch_beneficiary.village_id == 'NULL':
                    rch_beneficiary.village_id = 0
                rch_beneficiary.save()