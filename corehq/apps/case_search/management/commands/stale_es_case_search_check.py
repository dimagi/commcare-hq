import csv
from argparse import FileType
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from dimagi.utils.chunked import chunked
from dimagi.utils.parsing import string_to_datetime
from dimagi.utils.retry import retry_on

from corehq.apps.es import (
    CaseES,
    CaseSearchES,
    filters,
)
from corehq.apps.export.const import CASE_SCROLL_SIZE
from corehq.elastic import ESError


retry_on_es_timeout = retry_on(ESError, delays=[2**x for x in range(10)])


class Command(BaseCommand):
    help = """Checks for `server_modified_on` timestamp mismatches between `hqcases` and `case_search` indices."""

    def add_arguments(self, parser):
        parser.add_argument("--csv", action="store_true", default=False,
            help="Write output as CSV data instead of padded table.")
        parser.add_argument("-o", "--output", metavar="FILE", type=FileType("w"),
            default=self.stdout, help="Write output to %(metavar)s (default=STDOUT).")
        parser.add_argument("--id-limit", metavar="COUNT", type=int, default=500,
            help="Limit case_search queries to %(metavar)s IDs per query (default=%(default)s)")
        parser.add_argument("--mismatch-seconds", metavar="SECONDS", type=float,
            default=(10 * 60),  # 10 minutes
            help="Delta seconds for records to be considered a mismatch for " \
            "(default=%(default)s)")
        parser.add_argument("-s", "--since", metavar="YYYY-MM-DD",
            help="Query cases modified since %(metavar)s (default=NO_LIMIT)")
        parser.add_argument("domains", metavar="DOMAIN", nargs="*",
            help="Check timestamps for %(metavar)s")

    def handle(self, domains, since, mismatch_seconds, id_limit, **options):
        self.stderr.style_func = lambda x: x
        logger = StubLogger(self.stderr)
        # domains
        if not domains:
            domains = sorted(fetch_all_case_search_domains())
            logger.info("checking all %s case_search domains", len(domains))
        # since
        if since is None:
            date_msg = ""
            when = None
        else:
            date_msg = f" since {since}"
            try:
                when = datetime.strptime(f"{since}UTC", "%Y-%m-%d%Z")
            except ValueError:
                raise CommandError(f"invalid date: {since}")
        # warning condition if the `cases` document is newer than `case_search`
        warn_case_newer_than = timedelta(seconds=mismatch_seconds)

        table = Table(
            header=["domain", "case_id", "delta", "cases_smo", "case_search_smo"],
            max_col_width=36,
        )
        for domain in domains:
            # query the cases index
            cases = {}
            query = (CaseES()
                .domain(domain)
                .source(["case_id", "server_modified_on"])
                .size(CASE_SCROLL_SIZE))
            if when is not None:
                query = query.filter(filters.date_range("server_modified_on", gte=when))
            logger.info("fetching cases for domain %r%s ...", domain, date_msg)
            for case in query.scroll():
                cases[case["case_id"]] = string_to_datetime(case["server_modified_on"])
            logger.info("fetched %s cases", len(cases))

            # compare results to the case_search index
            case_searches = 0
            mismatches = 0
            logger.info("fetching case_searches ...")
            try:
                for case_search in fetch_case_searches(cases, id_limit):
                    case_searches += 1
                    case_id = case_search["_id"]
                    server_modified_on = string_to_datetime(case_search["server_modified_on"])
                    delta = cases[case_id] - server_modified_on
                    # we only care about case_searches whose
                    # `server_modified_on` is *older* (greater than)
                    if delta > warn_case_newer_than:
                        table.add_row([
                            domain,
                            case_id,
                            human_td(delta),
                            human_dt(cases[case_id]),
                            human_dt(server_modified_on),
                        ])
                        mismatches += 1
            finally:
                logger.info("fetched %s case_searches", case_searches)
                logger.info("found %s mismatched records for domain: %s", mismatches, domain)
        logger.info("done.")
        if options["csv"]:
            table.write_csv(options["output"])
        else:
            options["output"].write(table.render())


@retry_on_es_timeout
def fetch_all_case_search_domains():
    return (CaseSearchES()
        .terms_aggregation("domain.exact", "domain")
        .size(0)
        .run()
        .aggregations.domain.keys)


def fetch_case_searches(case_ids, chunksize):
    @retry_on_es_timeout
    def fetch_chunk(ids):
        return (CaseSearchES()
            .case_ids(ids)
            .source(["_id", "server_modified_on"])
            .size(len(ids))
            .run()
            .hits)
    for id_subset in chunked(case_ids, chunksize):
        yield from fetch_chunk(id_subset)


def human_dt(dt):
    return dt.strftime("%Y-%m-%d_%H:%M:%S")


def human_td(td):
    return str(td).rpartition(".")[0]


class StubLogger(object):

    def __init__(self, stream, datefmt="%Y-%m-%d %H:%M:%S",
                 format="[%(asctime)s] %(levelname)s: %(message)s"):
        self.stream = stream
        self.datefmt = datefmt
        self.format = format

    def _write_log(self, levelname, message, *args):
        attrs = dict(
            asctime=datetime.now().strftime(self.datefmt),
            levelname=levelname,
            message=(message % args),
        )
        rendered = self.format % attrs
        self.stream.write(rendered)

    def _make_level_method(levelname):
        def func(self, *args, **kw):
            self._write_log(levelname, *args, **kw)
        func.__name__ = levelname.lower()
        return func

    debug = _make_level_method("DEBUG")
    info = _make_level_method("INFO")
    warning = _make_level_method("WARNING")
    error = _make_level_method("ERROR")


class Table:
    """Convenience class for rendering tables with space-padded columns."""

    JUST_MAP = dict(c="center", l="ljust", r="rjust")

    def __init__(self, header=None, max_col_width=24):
        self.header = header
        self.max_col_width = max_col_width
        self.rows = []
        self.widths = []
        if header is not None:
            self.add_row(header)

    def add_row(self, row):
        """Add a row of fields to the table."""
        for index, value in enumerate(row):
            width = len(str(value))
            try:
                self.widths[index] = max(self.widths[index], width)
            except IndexError:
                self.widths.append(width)
        self.rows.append(row)

    def sort(self, *sorta, **sortkw):
        header = None if self.header is None else self.rows.pop(0)
        self.rows.sort(*sorta, **sortkw)
        if header is not None:
            self.rows.insert(0, header)

    def write_csv(self, file):
        writer = csv.writer(file)
        for row in self.rows:
            writer.writerow([str(c) for c in row])

    def render(self, column_sep=" ", just_key=[]):
        """Renders and returns the full table with whitespace-padded columns."""
        col_just = [self.JUST_MAP["l"]] * len(self.widths)  # init all
        for index, key in enumerate(just_key):
            col_just[index] = self.JUST_MAP[key]
        table = []
        for row in self.rows:
            padded = []
            for index, value in enumerate(row):
                just = col_just[index]
                width = min(self.widths[index], self.max_col_width)
                padded.append(getattr(str(value), just)(width))
            table.append(column_sep.join(padded).rstrip())
        return "\n".join(table) + "\n"
