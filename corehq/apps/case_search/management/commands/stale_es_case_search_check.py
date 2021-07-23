import csv
from argparse import FileType
from datetime import datetime, timedelta
from hashlib import md5

from django.core.management.base import BaseCommand, CommandError
from dimagi.utils.chunked import chunked
from dimagi.utils.parsing import string_to_datetime
from dimagi.utils.retry import retry_on

from corehq.apps.es import (
    CaseES,
    CaseSearchES,
)
from corehq.apps.export.const import CASE_SCROLL_SIZE
from corehq.elastic import ESError
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


retry_on_es_timeout = retry_on(ESError, delays=[2**x for x in range(10)])


class Command(BaseCommand):
    help = "Checks for `server_modified_on` timestamp mismatches between " \
           "`hqcases` and `case_search` indices."

    def add_arguments(self, parser):
        parser.add_argument("--csv", action="store_true", default=False,
            help="Write output as CSV data instead of padded table.")
        parser.add_argument("-o", "--output", metavar="FILE", type=FileType("w"),
            default=self.stdout, help="Write output to %(metavar)s (default=STDOUT).")
        parser.add_argument("-q", "--query-size", metavar="COUNT", type=int, default=1000,
            help="Limit queries to %(metavar)s case IDs per query (default=%(default)s)")
        parser.add_argument("--mismatch-seconds", metavar="SECONDS", type=float,
            default=(10 * 60),  # 10 minutes
            help="Delta seconds for records to be considered a mismatch for " \
            "(default=%(default)s)")
        parser.add_argument("-d", "--divide-key", metavar="a[b]",
            help="When running against all domains, only query domains whose "
                 "first character of 'md5 hexdigest of name' is within range 'a->b'.")
        parser.add_argument("-E", "--es-cases-cmp", action="store_true", default=False,
            help="Compare case_search documents against ES cases index (instead of Couch/SQL)")
        parser.add_argument("domains", metavar="DOMAIN", nargs="*",
            help="Check timestamps for %(metavar)s")

    def handle(self, domains, divide_key, mismatch_seconds, query_size, **options):
        self.stderr.style_func = lambda x: x
        logger = StubLogger(self.stderr)
        # domains
        all_cs_domains = sorted(fetch_all_case_search_domains())
        if domains:
            if divide_key:
                raise CommandError("--divide-key option is mutually exclusive "
                                   "with specified domains")
            for index in range(len(domains) - 1, -1, -1):
                if domains[index] not in all_cs_domains:
                    logger.info("skipping domain %r (not in case_search index)",
                                domains.pop(index))
        else:
            if divide_key:
                try:
                    domains = domain_subset(all_cs_domains, divide_key)
                except ValueError as exc:
                    raise CommandError(f"invalid divide-key: {exc!s}")
                which = f"{len(domains)} of"
            else:
                domains = all_cs_domains
                which = "all"
            logger.info("checking %s %s case_search domains", which, len(all_cs_domains))

        # warning condition if the `cases` document is newer than `case_search`
        warn_case_newer_than = timedelta(seconds=mismatch_seconds)

        table = Table(
            header=["domain", "case_id", "delta", "cases_smo", "case_search_smo"],
            max_col_width=36,
        )
        for domain in domains:
            logger.info("fetching cases for domain: %s", domain)
            # query all cases and modified date
            now = datetime.now()
            if options["es_cases_cmp"]:
                missing_ids = 0
                cases = {}
                for case_id, smo in get_case_ids_and_mod_escases(domain):
                    if case_id is None:
                        missing_ids += 1
                        continue
                    cases[case_id] = smo
                if missing_ids:
                    logger.warning("failed to fetch %s ES cases for domain: %s", missing_ids, domain)
            else:
                cases = dict(get_case_ids_and_mod_couchsql(domain, query_size))
            logger.info("fetched %s cases in %s", len(cases), datetime.now() - now)
            # compare results to the case_search index
            case_searches = 0
            mismatches = 0
            logger.info("fetching case_searches ...")
            try:
                for case_search in fetch_case_searches(list(cases), query_size):
                    case_searches += 1
                    case_id = case_search["_id"]
                    try:
                        smo_cs = string_to_datetime(case_search["server_modified_on"])
                    except KeyError:
                        smo_cs = None
                    smo_case = cases.pop(case_id)
                    try:
                        delta = smo_case - smo_cs
                    except TypeError:
                        try:
                            delta = smo_case.replace(tzinfo=smo_cs.tzinfo) - smo_cs
                        except TypeError:
                            delta = None
                    # we only care about case_searches whose
                    # `server_modified_on` is *older* (greater than)
                    if delta is None or delta > warn_case_newer_than:
                        table.add_row([
                            domain,
                            case_id,
                            human_td(delta),
                            human_dt(smo_case),
                            human_dt(smo_cs),
                        ])
                        mismatches += 1
                if cases:
                    logger.warning("found %s cases missing from case_search index", len(cases))
                    for case_id, smo_case in cases.items():
                        table.add_row([
                            domain,
                            case_id,
                            "n/a",
                            human_dt(smo_case),
                            "n/a",
                        ])
            finally:
                logger.info("fetched %s case_searches", case_searches)
                logger.info("found %s mismatched records for domain: %s", mismatches, domain)
        logger.info("done.")
        if options["csv"]:
            table.write_csv(options["output"])
        else:
            options["output"].write(table.render())


def domain_subset(domains, key):
    if len(key) not in (1, 2):
        raise ValueError(f"invalid length (must be 1 or 2 hex digits): {key}")
    key = (key * 2) if len(key) == 1 else key
    min = int(key[0], 16)
    max = int(key[1], 16)
    subset = []
    for name in domains:
        index = int(md5(name.encode("utf-8")).hexdigest()[0], 16)
        if min <= index and index <= max:
            subset.append(name)
    return subset


def get_case_ids_and_mod_escases(domain):
    query = (CaseES()
        .domain(domain)
        .source(["_id", "case_id", "server_modified_on"])
        .size(CASE_SCROLL_SIZE))
    for case in query.scroll():
        case_id = case.get("case_id", case.get("_id"))
        try:
            smo = string_to_datetime(case["server_modified_on"])
        except KeyError:
            smo = None
        yield case_id, smo


def get_case_ids_and_mod_couchsql(domain, chunksize):
    case_accessor = CaseAccessors(domain)
    for case_ids in chunked(case_accessor.get_case_ids_in_domain(), chunksize):
        yield from case_accessor.get_last_modified_dates(list(case_ids)).items()


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
    return "null" if dt is None else dt.strftime("%Y-%m-%d_%H:%M:%S")


def human_td(td):
    return "null" if td is None else str(td).rpartition(".")[0]


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
