import csv
import os
from argparse import FileType
from urllib.parse import urlparse, urlunparse

import requests
from django.core.management.base import BaseCommand, CommandError
from oauthlib.oauth2.rfc6749.errors import OAuth2Error
from requests.exceptions import HTTPError, RequestException, SSLError

from corehq.motech.models import ConnectionSettings
from corehq.util.argparse_types import validate_range
from corehq.util.log import with_progress_bar
from corehq.util.urlvalidate.ip_resolver import CannotResolveHost


IMPLICIT_HTTPS_PORT = 443


class Command(BaseCommand):

    help = "Make an HTTP HEAD request to configured MOTECH connections " \
           "to test the connectivity of each URL or verify connection domain " \
           "SSL certificates."

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        # disable special styling for STDERR
        self.stderr.style_func = self.stdout.style_func

    def add_arguments(self, parser):
        parser.add_argument("-c", "--ca-bundle", metavar="FILE",
            help="Use a custom CA trust store for SSL verifications.")
        parser.add_argument("--connect-timeout", metavar="SECONDS", type=float,
            action=validate_range(gt=0.0),
            help="Use custom HTTP connection timeout value.")
        parser.add_argument("--ssl-only", action="store_true", default=False,
            help="Skip normal connection checks and perform only SSL "
                 "verification tests against domains of connections with "
                 "verify-enabled HTTPS URLs.")
        parser.add_argument("-o", "--csv-out", metavar="FILE", default="-",
            type=FileType("w", encoding="utf-8"),
            help="Write failures to CSV %(metavar)s (default=STDOUT)")

    def handle(self, *args, **options):
        self.verbose = options["verbosity"] > 1
        timeout = options["connect_timeout"]
        castore = options["ca_bundle"]

        # sanity-check options
        if castore is not None and not os.path.isfile(castore):
            raise CommandError(f"Invalid CA store file: {castore}")

        # determine which verification method to use
        if options["ssl_only"]:
            iter_fails = self.verify_ssl_domains
        else:
            iter_fails = self.verify_connections

        failures = []
        conn_generator = with_progress_bar(
            list(ConnectionSettings.objects.order_by("url")),
            oneline=(not self.verbose),
            stream=self.stderr._out,  # OutputWrapper.write() does not play nice
        )
        request_kw = {
            "verify": (castore or True),
            "timeout": timeout,
        }
        for conn, exc in iter_fails(conn_generator, request_kw):
            code = getattr(getattr(exc, "response", None), "status_code", "err")
            failures.append((conn, code, exc.__class__.__name__, str(exc)))

        if failures:
            csv_rows = [[
                "domain",
                "setting name",
                "url",
                "error type",
                "error message",
            ]]
            self.console(f"ERROR: {len(failures)} failure(s):", self.style.ERROR)
            for conn, code, err, msg in failures:
                self.console(f"FAIL [{code}]: {conn.url}")
                csv_rows.append([conn.domain, conn.name, conn.url, err, msg])
            # write this last to keep logging separate (in case STDOUT is used)
            writer = csv.writer(options["csv_out"])
            writer.writerows(csv_rows)

    def console(self, msg, style_func=None, *write_args, **write_kw):
        """Write a message to the console (`self.stderr`).

        :param msg: str debug message to be written
        :param style_func: function passed verbatim to `self.stderr.write()`
        :param *write_args: args passed verbatim to `self.stderr.write()`
        :param **write_kw: kwargs passed verbatim to `self.stderr.write()`
        """
        self.stderr.write(msg, style_func, *write_args, **write_kw)

    def debug(self, msg):
        """Write a message to the console if verbose mode is enabled.

        :param msg: str debug message to be written
        """
        if self.verbose:
            self.console(msg)

    def log_totals(self, name, successes, total):
        """Write number of successes to console in a stylish way.

        :param name: str name of "things being verified"
        :param successes: int number of successful verifications
        :param total: int number of verification attempted
        """
        message = f"\nSuccessfully verified {successes} of {total} {name}"
        if total and not successes:
            style = self.style.ERROR
        elif total > successes:
            style = self.style.WARNING
        else:
            style = self.style.SUCCESS
        self.console(message, style)

    def verify_connections(self, connections, request_kw):
        """Test all connections.

        :param connections: iterable of ConnectionSettings objects
        :param request_kw: dict of kw args for `requests.request()` call
        :yields: (connection, exception) tuples for connection test failures
        """
        total = 0
        successes = 0
        for connection in connections:
            total += 1
            requests = connection.get_requests()
            self.debug(f"HEAD {connection.url}")
            try:
                # `send_request_unlogged()`` overrides `verify` argument if
                # verification is disabled for this connection object.
                requests.send_request_unlogged("HEAD", connection.url,
                                               raise_for_status=True,
                                               **request_kw)
                successes += 1
            except HTTPError as exc:
                if exc.response.status_code == 405:  # ignore method not allowed
                    successes += 1
                else:
                    yield connection, exc
            except (CannotResolveHost, OAuth2Error, RequestException) as exc:
                yield connection, exc
        self.log_totals("connections", successes, total)

    def verify_ssl_domains(self, connections, request_kw):
        """Verify SSL certificates for unique connection domains.

        :param connections: iterable of ConnectionSettings objects
        :param request_kw: dict of kw args for `requests.request()` call
        :yields: (connection, exception) tuples for SSL verification failures
        """
        successes = 0
        errors = []
        checked = set()
        for connection in connections:
            if connection.skip_cert_verify:
                self.debug(f"skipping (verify disabled): {connection.url}")
                continue
            urlparts = urlparse(connection.url)
            if urlparts.scheme != "https":
                if urlparts.scheme == "http":
                    self.debug(f"skipping (non-SSL): {connection.url}")
                else:
                    self.debug(f"skipping (unknown scheme): {connection.url}")
                continue
            hostname, x, port = urlparts.netloc.partition(":")
            if not port:
                # Key `checked` set by explicit port numbers to avoid duplicate
                # hits on domains where multiple URLs exist, some with the
                # port implied and others with port 443 set explicitly.
                port = IMPLICIT_HTTPS_PORT
            uniq = (hostname, int(port))
            if uniq in checked:
                continue
            checked.add(uniq)
            url = urlunparse(("https", urlparts.netloc, "/", "", "", ""))
            self.debug(f"HEAD {url}")
            try:
                requests.head(url, **request_kw)
                successes += 1
            except HTTPError:
                # HTTP errors mean SSL success
                successes += 1
            except SSLError as exc:
                # SSL errors are the only "failure" mode
                yield connection, exc
            except RequestException as exc:
                # other exceptions are logged as errors, but not reported as
                # "SSL failures"
                errors.append((url, exc.__class__.__name__))
        if errors:
            self.console(f"WARNING: encountered {len(errors)} request error(s):",
                self.style.NOTICE)
            for url, msg in errors:
                self.console(f"{msg}: {url}")
        self.log_totals("domains", successes, len(checked))
