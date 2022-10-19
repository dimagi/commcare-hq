import csv
import os
from argparse import FileType
from itertools import chain
from urllib.parse import urlparse, urlunparse

import requests
from attrs import define, field
from django.core.management.base import BaseCommand, CommandError
from oauthlib.oauth2.rfc6749.errors import OAuth2Error
from requests.exceptions import HTTPError, RequestException, SSLError

from corehq.motech.models import ConnectionSettings
from corehq.util.argparse_types import validate_range
from corehq.util.log import with_progress_bar
from corehq.util.urlvalidate.ip_resolver import CannotResolveHost
from corehq.util.urlvalidate.urlvalidate import (
    PossibleSSRFAttempt,
    validate_user_input_url,
)

IMPLICIT_HTTPS_PORT = 443


class Command(BaseCommand):

    help = """
        Make an HTTP HEAD request to HTTP endpoints to test the
        connectivity of each URL or verify connection domain
        SSL certificates.
        """

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

        endpoints = with_progress_bar(
            list(self.iter_endpoints()),
            oneline=(not self.verbose),
            stream=self.stderr._out,  # OutputWrapper.write() does not play nice
        )
        results = []
        request_kw = {
            "verify": (castore or True),
            "timeout": timeout,
        }
        for end in endpoints:
            results.append(self.verify_ssl(end, request_kw))

        failures = [r for r in results if r.failure]
        errors = [r for r in results if r.error]
        success_count = len(results) - len(failures) - len(errors)
        self.log_totals("domains", success_count, len(results))
        if errors:
            self.console(f"WARNING: encountered {len(errors)} request error(s):", self.style.NOTICE)
            for result in errors:
                err, msg = result.error
                self.console(f"{result.endpoint.url} - {err}: {msg}")
        if failures:
            csv_rows = [[
                "domain",
                "setting name",
                "url",
                "error type",
                "error message",
            ]]
            self.console(f"ERROR: {len(failures)} failure(s):", self.style.ERROR)
            for result in failures:
                end = result.endpoint
                self.console(f"FAIL [{result.status_code}]: {end.url}")
                err, msg = result.failure
                csv_rows.append([end.domain, end.name, end.url, err, msg])
            # write this last to keep logging separate (in case STDOUT is used)
            writer = csv.writer(options["csv_out"])
            writer.writerows(csv_rows)

    def iter_endpoints(self):
        seen = set()
        for end in chain(self.iter_motech_endpoints(), self.iter_sms_endpoints()):
            if end.scheme != "https":
                if end.scheme == "http":
                    self.debug(f"skipping (non-SSL): {end.url}")
                else:
                    self.debug(f"skipping (unknown scheme): {end.url}")
                continue
            if end.uniq not in seen:
                seen.add(end.uniq)
                yield end

    def iter_motech_endpoints(self):
        for connection in ConnectionSettings.objects.order_by("url"):
            if connection.skip_cert_verify:
                self.debug(f"skipping (verify disabled): {connection.url}")
                continue
            yield Endpoint(connection.url, connection.domain, connection.name)

    def iter_sms_endpoints(self):
        raise NotImplementedError("TODO")

    def verify_ssl(self, end, request_kw):
        """Verify SSL certificates for unique connection domains.

        :param connections: iterable of ConnectionSettings objects
        :param request_kw: dict of kw args for `requests.request()` call
        :yields: (connection, exception) tuples for SSL verification failures
        """
        url = urlunparse(("https", end.netloc, "/", "", "", ""))
        try:
            validate_user_input_url(url)
        except (CannotResolveHost, PossibleSSRFAttempt) as exc:
            return Result(end, "error", error=exc_tuple(exc))
        self.debug(f"HEAD {url}")
        try:
            response = requests.head(url, **request_kw)
        except HTTPError as exc:
            # HTTP errors mean SSL success
            response = exc.response
        except SSLError as exc:
            # SSL errors are the only "failure" mode
            return Result(end, "error", failure=exc_tuple(exc))
        except RequestException as exc:
            # other exceptions are logged as errors, but not reported as "SSL failures"
            return Result(end, "error", error=exc_tuple(exc))
        return Result(end, response.status_code)

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


@define(slots=False)
class Endpoint:
    url = field()
    domain = field()
    name = field()

    def __attrs_post_init__(self):
        urlparts = urlparse(self.url or "")
        hostname, x, port = urlparts.netloc.partition(":")
        if not port:
            port = IMPLICIT_HTTPS_PORT
        self.scheme = urlparts.scheme
        self.netloc = urlparts.netloc
        self.uniq = (hostname, int(port))


@define
class Result:
    endpoint = field()
    status_code = field()
    failure = field(default=None)
    error = field(default=None)


def exc_tuple(exc):
    return type(exc).__name__, str(exc)
