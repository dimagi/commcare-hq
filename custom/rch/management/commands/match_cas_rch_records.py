from django.core.management import BaseCommand
from corehq.apps.es.case_search import CaseSearchES
from custom.rch.models import RCHRecord


class Command(BaseCommand):
    def handle(self, *args, **options):
        mother_rch_beneficiaries = RCHRecord.objects.filter(doc_type=0)
        for rch_record in mother_rch_beneficiaries.all():
            query = (CaseSearchES().domain('icds-cas').
                     case_property_query("name", rch_record.name, fuzzy=True).
                     case_property_query("rch_id", rch_record.rch_id, fuzzy=True).
                     case_property_query("dob", rch_record.dob.strftime('%Y-%m-%d')).
                     case_property_query("phone_number", rch_record.prop_doc.properties['Mobile_no'])
                     )

            if query.run().hits:
                print 'found match', rch_record.name, rch_record.id

