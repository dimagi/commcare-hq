import csv

from django.core.management.base import BaseCommand
from requests import RequestException, HTTPError

from corehq.motech.models import ConnectionSettings
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    help = "Make an HTTP HEAD request to all configured MOTECH connections to test the connectivity" \
           "and SSL validation (if connection setting has not disabled SSL validation)."

    def handle(self, *args, **options):
        failures = []
        connections = list(ConnectionSettings.objects.all())
        for connection in with_progress_bar(connections):
            requests = connection.get_requests()
            try:
                requests.send_request_unlogged("HEAD", connection.url, raise_for_status=True)
            except HTTPError as e:
                if e.response.status_code != 405:  # ignore method not allowed
                    failures.append((connection, e.__class__.__name__, str(e)))
            except RequestException as e:
                failures.append((connection, e.__class__.__name__, str(e)))

        if not failures:
            print("\nAll connection tests successful")
        else:
            print(f"\n{len(failures)} connection settings failed\n")
            writer = csv.writer(self.stdout)
            writer.writerow(["domain", "setting name", "url", "error type", "error message"])
            for connection, error_type, error_message in failures:
                writer.writerow([connection.domain, connection.name, connection.url, error_type, error_message])
