import re
import os
from datetime import datetime
from django.core.management.base import BaseCommand

from corehq.apps.export.export import get_export_file
from corehq.apps.export.utils import get_export

from corehq.util.view_utils import get_form_or_404

from corehq.apps.domain.models import Domain
from corehq.apps.export.filters import ModifiedOnRangeFilter, ReceivedOnRangeFilter


class Command(BaseCommand):
    help = 'Pull data linked to a request'

    def add_arguments(self, parser):
        parser.add_argument('requestsCSV')
        parser.add_argument('--path_prefix', default=os.getcwd())

    def handle(self, *args, **options):
        requests = parse_requests(options['requestsCSV'])
        process_requests(requests, options['path_prefix'])


def process_requests(requests, path_prefix):
    current_time = datetime.now()
    for request in requests:
        try:
            process_request(request, path_prefix, current_time)
        except Exception as e:
            print(f'Error occurred with request {request["url"]}')
            print(e)


def process_request(request, path_prefix, current_time):
    if not path_prefix:
        path_prefix = os.getcwd()

    pattern = re.compile(
        r'https?://(?:.*)/a/([^/]+)/data/export/custom/new/(form|case)/download/([^/]+)/?')

    match = pattern.match(request['url'])
    if match:
        domain = match.group(1)
        export_type = match.group(2)
        export_id = match.group(3)
        end_date = datetime.strptime(request['date'], '%m/%d/%Y') if export_type == 'case' else current_time
        path = process_export(domain, export_type, export_id, end_date, path_prefix)
        print(f'Saved export at: {path}')
        return

    read_form_regex = re.compile(
        r'https?://(?:.*)/a/([^/]+)/reports/form_data/([^/]+)/?'
    )

    match = read_form_regex.match(request['url'])
    if match:
        domain = match.group(1)
        form_id = match.group(2)
        path = process_form_data(domain, form_id, path_prefix)
        print(f'Saved form at: {path}')
        return

    print('no matches')


def process_export(domain, export_type, export_id, end_date, path_prefix):
    print(f'processing {export_type} {export_id}')
    start_date = get_domain_start_date(domain)
    if export_type == 'case':
        filters = [ModifiedOnRangeFilter(gte=start_date, lte=end_date)]
    else:
        filters = [ReceivedOnRangeFilter(gte=start_date, lte=end_date)]
    export_instance = get_export(export_type, domain, export_id)
    filename = sanitize_filename(f'{export_instance.name} - {export_id}.xlsx')
    path = os.path.join(path_prefix, filename)
    get_export_file([export_instance], filters, path)

    return path


def process_form_data(domain, form_id, path_prefix):
    print(f'processing form {form_id}')
    instance = get_form_or_404(domain, form_id)
    if not instance:
        raise Exception(f'No form found for {form_id}')

    filename = sanitize_filename(f'{instance.name} - {instance.form_id}.xml')
    path = os.path.join(path_prefix, filename)

    with open(path, 'wb') as f:
        f.write(instance.get_xml())

    return path


def sanitize_filename(filename):
    return filename.replace(os.sep, '-')


def get_domain_start_date(domain):
    return Domain.get_by_name(domain).date_created


def parse_requests(filename):
    requests = []
    with open(filename, 'r') as f:
        f.readline()  # Discard, this is the header
        line = f.readline().strip()
        while line:
            request_url, date_requested = line.split(',')
            requests.append({
                'url': request_url,
                'date': date_requested
            })

            line = f.readline()

    return requests
