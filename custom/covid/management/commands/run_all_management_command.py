import csv
from gevent.pool import Pool

from django.core.management.base import BaseCommand
from django.core.management import call_command


DEVICE_ID = __name__ + ".run_all_management_command"


def run_command(command, *args, location=None):
    try:
        if location is None:
            call_command(command, *args)
        else:
            call_command(command, *args, location=location)
    except Exception as e:
        return False, command, args, e
    return True, command, args, None


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('csv_file')

    def handle(self, csv_file, **options):
        domains = set()
        location_ids = {}
        with open(csv_file, newline='') as file:
            reader = csv.DictReader(file)
            for row in reader:
                domains.add(row['domain'])
                locations = []
                if row['location1'] != '':
                    locations.append(row['location1'])
                if row['location2'] != '':
                    locations.append(row['location2'])
                location_ids[row['domain']] = locations

        total_jobs = []
        jobs = []
        pool = Pool(20)
        for domain in domains:
            jobs.append(pool.spawn(run_command, 'update_case_index_relationship', domain, 'contact'))
            jobs.append(pool.spawn(run_command, 'add_hq_user_id_to_case', domain, 'checkin'))
            jobs.append(pool.spawn(run_command, 'update_owner_ids', domain, 'investigation'))
            jobs.append(pool.spawn(run_command, 'update_owner_ids', domain, 'checkin'))
        pool.join()
        total_jobs.extend(jobs)

        jobs = []
        second_pool = Pool(20)
        for domain in domains:
            for location in location_ids[domain]:
                jobs.append(second_pool.spawn(run_command, 'add_assignment_cases', domain, 'patient',
                                              location=location))
                jobs.append(second_pool.spawn(run_command, 'add_assignment_cases', domain, 'contact',
                                              location=location))
        pool.join()
        total_jobs.extend(jobs)

        for job in total_jobs:
            success, command, args, exception = job.get()
            if success:
                print("SUCCESS: {} command for {}".format(command, args))
            else:
                print("COMMAND FAILED: {} while running {} for {})".format(exception, command, args))
