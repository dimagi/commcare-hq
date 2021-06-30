from gevent.pool import Pool

from django.core.management.base import BaseCommand, CommandError

from corehq.motech.repeaters.dbaccessors import get_couch_repeat_record_ids_by_payload_id, get_domains_that_have_repeat_records
from coreqh.motech.reepaters.models import RepeatRecord

class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('startdate')
        parser.add_argument('--domain')
        parser.add_argument('--mirror_domains', action='store_true')
        parser.add_argument('--fix', action='store_true')

    def handle(self, startdate, domain, mirror_domains, fix, **options):
        if mirror_domains and not domain:
            raise CommandError('cannot use mirror domains without specifying domain')
        if domain:
            domains = [domain]
            if mirror_domains:
                domains.extend(DomainPermissionsMirror.mirror_domains(domain))
        else:
            domains = get_domains_that_have_repeat_records()
        p = Pool(20)
        jobs = []
        for d in domains:
            j = p.spawn(test_inconsistency, d, startdate, fix)
            jobs.append(j)
        p.join()
        for j in jobs:
            try:
                j.get()
            except:
                print('Error in {}'.format(j))

    def test_inconsistency(self, domain, startdate, fix):
        bad_cases = []
        case_ids = [c['_id'] for c in self.get_case_ids_in_domain_since_date(domain, startdate)]
        count = 0
        for i in case_ids:
            if count % 100 == 0:
                print('{}/{}'.format(count, len(case_ids)))
            repeater_counts = set()
            records = set()
            for n in range(100):
                repeaters = get_couch_repeat_record_ids_by_payload_id(domain, i)
                repeater_counts.add(len(repeaters))
                records.add(set(repeaters))
            if len(repeater_counts) > 1:
                bad_cases.append(i)
            if fix:
                for c in records:
                    RepeatRecord.get(record)
            count += 1
        print('Found {} cases with inconsistent records'.format(len(bad_cases)))


    def get_case_ids_in_domain_since_date(self, domain, startdate):
        return CaseES(es_instance_alias='export').domain(domain).server_modified_range(gte=startdate).source(['_id']).run().hits
