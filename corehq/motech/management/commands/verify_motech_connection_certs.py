from urllib.parse import urlparse, urlunparse

import requests
from django.core.management.base import BaseCommand
from requests.exceptions import SSLError

from corehq.motech.models import ConnectionSettings
from corehq.util.log import with_progress_bar


IMPLICIT_HTTPS_PORT = 443


class Command(BaseCommand):

    help = "Verify MOTECH connection certificates by performing an HTTP HEAD " \
           "request to all unique domains where the URL method == HTTPS and " \
           "SSL validation is enabled."

    def add_arguments(self, parser):
        parser.add_argument("-c", "--ca-bundle", metavar="FILE",
            help="Use a custom CA trust store for SSL verifications.")
        parser.add_argument("--connect-timeout", metavar="SECONDS", type=float,
            default=None, help="Use custom HTTP connection timeout value.")

    def handle(self, *args, **options):
        verbose = options["verbosity"] > 1
        timeout = options["connect_timeout"]
        castore = options["ca_bundle"]

        def debug(msg):
            if verbose:
                self.stdout.write(msg)

        netlocs = {}
        for connection in ConnectionSettings.objects.all():
            if connection.skip_cert_verify:
                debug(f"skipping (verify disabled): {connection.url}")
                continue
            urlparts = urlparse(connection.url)
            if urlparts.scheme == "https":
                hostname, x, port = urlparts.netloc.partition(":")
                if not port:
                    # Key URL dict by explicit port numbers to avoid duplicate
                    # hits on domains where multiple URLs exist, some with the
                    # port implied and others with port 443 set explicitly.
                    port = IMPLICIT_HTTPS_PORT
                root_url = urlunparse(("https", urlparts.netloc, "/", "", "", ""))
                netlocs.setdefault((hostname, int(port)), root_url)
            elif urlparts.scheme == "http":
                debug(f"skipping (non-SSL): {connection.url}")
            else:
                debug(f"skipping (unknown scheme): {connection.url}")

        errors = []
        failures = []
        urls = [v for (k, v) in sorted(netlocs.items())]
        for url in with_progress_bar(urls, oneline=(not verbose)):
            try:
                debug(f"HEAD {url}")
                requests.head(url, verify=(castore or True), timeout=timeout)
            except SSLError:
                failures.append(url)
            except requests.RequestException as exc:
                errors.append((url, str(exc)))

        if errors:
            self.stdout.write(f"{len(errors)} HTTP error(s):")
            for url, msg in errors:
                self.stderr.write(f"WARNING: {url} {msg}", self.style.NOTICE)

        if failures:
            self.stdout.write(f"{len(failures)} SSL verification failure(s):")
            for url in failures:
                self.stdout.write(f"FAIL: {url}", self.style.ERROR)

        total = len(urls)
        successes = total - (len(failures) + len(errors))
        final_msg = f"\nSuccessfully verified {successes} of {total} domain(s)"
        if total and not successes:
            style = self.style.ERROR
        elif total > successes:
            style = self.style.WARNING
        else:
            style = self.style.SUCCESS
        self.stdout.write(final_msg, style)
