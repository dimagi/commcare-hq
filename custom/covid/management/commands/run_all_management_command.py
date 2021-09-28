import csv
from gevent.pool import Pool

from django.core.management.base import BaseCommand
from django.core.management import call_command
from datetime import datetime


DEVICE_ID = __name__ + ".run_all_management_command"


def run_command(command, *args, location=None, inactive_location=None, username=None, output_file=None):
    kwargs = {'username': username, 'output_file': output_file}
    try:
        if inactive_location is not None:
            kwargs['inactive_location'] = inactive_location
        if location is not None:
            kwargs['location'] = location
        call_command(command, *args, **kwargs)
    except Exception as e:
        return False, command, args, e
    return True, command, args, None


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('csv_file')
        parser.add_argument('--only-inactive', action='store_true', default=False)
        parser.add_argument('--username', type=str, default=None)
        parser.add_argument('--output-file', type=str, default=None)

    def handle(self, csv_file, **options):
        domains = []
        location_ids = {}
        with open(csv_file, newline='') as file:
            reader = csv.DictReader(file)
            for row in reader:
                domains.append(row['domain'])
                locations = {'active': {}, 'inactive': ''}
                if row['non_traveler_active_location_id'] != '':
                    locations['active']['non_traveler'] = (row['non_traveler_active_location_id'])
                if row['traveler_active_location_id'] != '':
                    locations['active']['traveler'] = (row['traveler_active_location_id'])
                locations['inactive'] = row['inactive_location_id']
                location_ids[row['domain']] = locations

        username = options["username"]
        output_file_name = options["output_file"]
        start_time = datetime.utcnow()
        if output_file_name:
            with open(output_file_name, "a") as output_file:
                output_file.write(f"Updated {len(domains)} domains \n")

        if len(set(domains)) != len(domains):
            domains = set(domains)
            print("Rows with duplicate domains were found from csv file. The commands for each domains will"
                  " run differently than the order of the csv file.")

        total_jobs = []
        jobs = []
        pool = Pool(20)
        if options["only_inactive"]:
            for domain in domains:
                kwargs = {'inactive_location': location_ids[domain]['inactive'], 'username': username,
                          'output_file': output_file_name}
                if 'traveler' in location_ids[domain]['active']:
                    kwargs['location'] = location_ids[domain]['active']['traveler']
                jobs.append(pool.spawn(run_command, 'update_case_index_relationship', domain, 'contact',
                                       **kwargs))
            pool.join()
            total_jobs.extend(jobs)
        else:
            for domain in domains:
                kwargs = {'username': username, 'output_file': output_file_name}
                if 'traveler' in location_ids[domain]['active']:
                    kwargs['location'] = location_ids[domain]['active']['traveler']
                jobs.append(pool.spawn(run_command, 'update_case_index_relationship', domain, 'contact', **kwargs))
                jobs.append(pool.spawn(run_command, 'add_hq_user_id_to_case', domain, 'checkin',
                                       username=username, output_file=output_file_name))
                jobs.append(pool.spawn(run_command, 'update_owner_ids', domain, 'investigation',
                                       username=username, output_file=output_file_name))
                jobs.append(pool.spawn(run_command, 'update_owner_ids', domain, 'checkin',
                                       username=username, output_file=output_file_name))
            pool.join()
            total_jobs.extend(jobs)

            jobs = []
            second_pool = Pool(20)
            for domain in domains:
                for location in location_ids[domain]['active'].values():
                    kwargs = {'location': location, 'username': username, 'output_file': output_file_name}
                    jobs.append(second_pool.spawn(run_command, 'add_assignment_cases', domain, 'patient',
                                                  **kwargs))
                    jobs.append(second_pool.spawn(run_command, 'add_assignment_cases', domain, 'contact',
                                                  **kwargs))
            second_pool.join()
            total_jobs.extend(jobs)

        for job in total_jobs:
            success, command, args, exception = job.get()
            if success:
                print("SUCCESS: {} command for {}".format(command, args))
            else:
                print("COMMAND FAILED: {} while running {} for {})".format(exception, command, args))

        if output_file_name:
            with open(output_file_name, "a") as output_file:
                output_file.write(f"Script start time: {start_time}\n")
                output_file.write(f"Script end time: {datetime.utcnow()}\n")
