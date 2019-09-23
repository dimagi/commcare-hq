import csv
import logging
import re
import sys
from collections import defaultdict, OrderedDict
from contextlib import contextmanager
from functools import partial
from itertools import chain

from six.moves.urllib.parse import unquote

from couchdbkit.exceptions import ResourceNotFound
from django.core.management import BaseCommand

from corehq.apps.hqadmin.views.data import get_db_from_db_name
from corehq.blobs import get_blob_db
from corehq.blobs.exceptions import NotFound
from corehq.util.decorators import change_log_level
from corehq.util.log import with_progress_bar


USAGE = "Usage: ./manage.py blob_storage_report [options] FILE [FILE ...]"


class Command(BaseCommand):
    """Report blob storage change over time using Riak CS access logs

    Usage: ./manage.py blob_storage_report [options] FILE [FILE ...]
    """
    help = USAGE

    def add_arguments(self, parser):
        parser.add_argument(
            "files",
            nargs="+",
            help="Riak CS access logs. Use - for stdin.",
        )
        parser.add_argument(
            "-o", "--output-file",
            default=sys.stdout,
            help="Write output to file.",
        )
        parser.add_argument(
            "--csv",
            action="store_true",
            default=False,
            dest="write_csv",
            help="Output report in CSV format.",
        )
        parser.add_argument(
            "-s", "--sample-size",
            type=int,
            default=500,
            help="Sample size.",
        )
        parser.add_argument(
            "-d", "--default-only",
            action="store_true",
            help="Ignore all except the default bucket.",
        )
        parser.add_argument(
            "--list-blob-ids",
            action="store_true",
            help="List blob ids in output (--output-file recommended).",
        )

    @change_log_level('boto3', logging.WARNING)
    @change_log_level('botocore', logging.WARNING)
    def handle(self, files, output_file, write_csv, sample_size, default_only,
               list_blob_ids, **options):

        print("WARNING this report has not been adapted to the new blob db "
              "metadata API, and therefore is probably broken.")

        print("Loading PUT requests from access logs...", file=sys.stderr)
        data = accumulate_put_requests(files)
        sizes, samples_by_type = get_blob_sizes(data, sample_size, default_only)

        with make_row_writer(output_file, write_csv) as write:
            report_blobs_by_type(data, sizes, samples_by_type, write)
            report_blob_sizes(data, sizes, samples_by_type, write)
            report_blob_sizes(data, sizes, samples_by_type, write, summarize=True)
            if list_blob_ids:
                report_blob_ids(sizes, write)


def report_blobs_by_type(data, sizes, samples_by_type, write):
    """report on number of new blobs by blob bucket"""
    assert len(data) < 100, len(data)
    bucket_missing = defaultdict(int)
    type_missing = defaultdict(int)
    for domain_sizes in sizes.values():
        for size in domain_sizes:
            if size.length is UNKNOWN:
                bucket_missing[size.bucket] += 1
                type_missing[size.doc_type] += 1
    write(["BUCKET", "BLOB COUNT", "NOT FOUND"])
    for bucket, key_list in sorted(data.items()):
        if bucket not in samples_by_type:
            continue
        write([bucket, len(key_list), bucket_missing.get(bucket, "")])
        for doc_type, n_samples in sorted(samples_by_type[bucket].items()):
            write(["  " + doc_type, n_samples, type_missing.get(doc_type, "")])
    write([])


def report_blob_sizes(data, sizes, samples_by_type, write, summarize=False):
    """report blob type, number of blobs, total size grouped by domain"""
    def iter_headers(by_domain):
        for domain in by_domain:
            yield domain
            yield "MEAN"
            yield "COUNT"

    def iter_sizes(doc_type, domain_sizes, totals):
        for domain in by_domain:
            blob_sizes = domain_sizes[domain]
            numerics = [s.length for s in blob_sizes if s.length is not UNKNOWN]
            if numerics:
                bucket = blob_sizes[0].bucket
                bucket_samples = sum(samples_by_type[bucket].values())
                mean_size = int(mean(numerics))
                est_size = (
                    mean_size *
                    len(data[bucket]) *                 # number blobs in bucket
                    (len(numerics) / bucket_samples)    # porportion of samples
                )
            else:
                mean_size = 0
                est_size = 0
            found_of_total = "{}/{}".format(len(numerics), len(blob_sizes))
            totals[domain]["size"] += est_size
            totals[domain]["found"] += len(numerics)
            totals[domain]["count"] += len(blob_sizes)
            yield sizeof_fmt(est_size)
            yield sizeof_fmt(mean_size)
            yield found_of_total if blob_sizes else "-"  # FOUND/TOTAL

    def iter_totals(totals):
        yield sizeof_fmt(sum(t["size"] for t in totals.values()))
        for domain in by_domain:
            yield sizeof_fmt(totals[domain]["size"])
            yield ""
            yield "{found}/{count}".format(**totals[domain])

    def sumlens(item):
        return -sum(s.length for s in item[1] if s.length is not UNKNOWN)

    if summarize:
        sizes = {"EST SIZE": list(chain.from_iterable(sizes.values()))}

    # get top five domains + all others combined
    OTHER = "OTHER"
    by_domain = OrderedDict()
    by_type = defaultdict(lambda: defaultdict(list))
    for i, (domain, domain_sizes) in enumerate(sorted(sizes.items(), key=sumlens)):
        if i < 5:
            by_domain[domain] = domain_sizes
        else:
            if i == 5:
                by_domain[OTHER] = []
            by_domain[OTHER].extend(domain_sizes)
            domain = OTHER
        for size in domain_sizes:
            by_type[size.doc_type][domain].append(size)

    def key(item):
        return sum(sumlens(["ignored", sizes]) for sizes in item[1].values())

    totals = {domain: {
        "size": 0,
        "found": 0,
        "count": 0,
    } for domain in by_domain}
    if summarize:
        write(["SUMMARY"])
    else:
        write(["Storage use based on sampled estimates (may be inaccurate)"])
    write(["DOC_TYPE"] + list(iter_headers(by_domain)))
    for doc_type, domain_sizes in sorted(by_type.items(), key=key):
        write([doc_type] + list(iter_sizes(doc_type, domain_sizes, totals)))
    write(["---"] + ["---" for x in iter_headers(by_domain)])
    write(list(iter_totals(totals)))
    write([])


def report_blob_ids(sizes, write):
    def iter_sizes(sizes):
        for domain_sizes in sizes.values():
            for size in domain_sizes:
                yield size

    def key(size):
        length = 0 if size.length is UNKNOWN else size.length
        return size.bucket, size.domain, size.doc_type, -length

    write("BUCKET DOMAIN DOC_TYPE SIZE BLOB_ID".split())
    for size in sorted(iter_sizes(sizes), key=key):
        write([
            size.bucket,
            size.domain,
            size.doc_type,
            sizeof_fmt(size.length) if size.length is not UNKNOWN else "",
            size.blob_id,
        ])
    write([])


def accumulate_put_requests(files):
    # data[blobdb_bucket] = set([tuple_of_blob_id_parts, ...])
    data = defaultdict(set)
    for filepath in files:
        if filepath == "-":
            load_puts(sys.stdin, data)
        else:
            with open(filepath, "r", encoding='utf-8') as fileobj:
                load_puts(fileobj, data)
    return data


def get_blob_sizes(data, sample_size, default_only):
    # get domain, blob type, and blob size for each put request (or a sample of them)
    def iter_samples(bucket, keys_list):
        for i, keys in enumerate(keys_list):
            if i >= sample_size:
                break
            get_blob_size = SIZE_GETTERS.get(bucket)
            if get_blob_size is not None:
                size = get_blob_size(bucket, *keys)
            else:
                size = get_default_blob_size(bucket, "/".join(keys))
            yield size

    sizes = defaultdict(list)  # {domain: [<BlobSize>, ...], ...}
    samples_by_type = {}  # {bucket: {<doc_type>: <n_samples>, ...}, ...}
    with_progress = partial(
        with_progress_bar,
        oneline="concise",
        stream=sys.stderr,
        step=1,
    )
    for bucket, keys_list in sorted(data.items()):
        counts = defaultdict(int)  # {<doc_type>: <n_samples>, ...}
        length = min(sample_size, len(keys_list))
        if default_only:
            if bucket != "_default":
                continue
            keys_list = (k for k in keys_list if not k[0].startswith("restore-response-"))
        samples = iter_samples(bucket, keys_list)
        for size in with_progress(samples, length, prefix=bucket):
            sizes[size.domain].append(size)
            counts[size.doc_type] += 1
        samples_by_type[bucket] = dict(counts)
    print("", file=sys.stderr)
    return sizes, samples_by_type


def get_couch_blob_size(db_name, bucket, doc_id, blob_id):
    doc = lookup_doc(doc_id, db_name)
    key = "/".join([doc_id, blob_id])
    if doc is None:
        return get_default_blob_size(bucket, key)
    domain = doc.get("domain", UNKNOWN)
    doc_type = doc.get("doc_type", UNKNOWN)
    for blob in doc["external_blobs"].values():
        if blob_id == blob["id"]:
            try:
                length = blob["length"]
                break
            except KeyError:
                pass
    else:
        size = get_default_blob_size(bucket, key)
        length = size.length
    return BlobSize(domain, doc_type, length, bucket, key)


def get_form_blob_size(bucket, attachment_id, subkey):
    # can't get domain: cannot get attachment metadata from blob id because
    # the metadata is sharded by form_id, which we do not have
    blob_id = "/".join([attachment_id, subkey])
    size = get_default_blob_size(bucket, blob_id)
    return BlobSize(UNKNOWN, "form", size.length, bucket, blob_id)


def get_default_blob_size(bucket, blob_id):
    try:
        length = get_blob_db().size(blob_id, bucket)
    except NotFound:
        length = UNKNOWN
    if blob_id.startswith("restore-response-"):
        return BlobSize(UNKNOWN, "restore", length, bucket, blob_id)
    return BlobSize(UNKNOWN, bucket, length, bucket, blob_id)


UNKNOWN = "(unknown)"
NOTFOUND = "(notfound)"
SIZE_GETTERS = {
    "_default": get_default_blob_size,
    "commcarehq": lambda *args: get_couch_blob_size("commcarehq", *args),
    "commcarehq__apps": lambda *args: get_couch_blob_size("apps", *args),
    "commcarehq__meta": lambda *args: get_couch_blob_size("meta", *args),
    "form": get_form_blob_size,
}


class BlobSize(object):

    def __init__(self, domain, doc_type, length, bucket, blob_id):
        self.domain = domain
        self.doc_type = doc_type
        self.length = length
        self.bucket = bucket
        self.blob_id = blob_id


def lookup_doc(doc_id, db_name):
    db = get_db_from_db_name(db_name)
    try:
        return db.get(doc_id)
    except ResourceNotFound:
        return None


def load_puts(fileobj, data):
    put_expr = re.compile(r"PUT /buckets/blobdb/objects/(.*) HTTP/1\.")
    for line in fileobj:
        match = put_expr.search(line)
        if not match:
            continue
        blob_path = unquote(match.group(1))
        parts = blob_path.split("/")
        if parts[0].startswith(("form", "commcarehq")):
            if len(parts) > 3 and parts[3] == "uploads":
                parts = parts[:3]
            assert len(parts) == 3, parts
            data[parts[0]].add((parts[1], parts[2]))
        else:
            if len(parts) > 2 and parts[2] == "uploads":
                parts = parts[:2]
            assert len(parts) == 2, parts
            data[parts[0]].add((parts[1],))


@contextmanager
def make_row_writer(output_file, write_csv):
    def make_row_widths_writer(rows, output_file):
        widths = [len(str(item)) for item in rows[0]]
        for row in rows[1:]:
            for i, item in enumerate(row):
                length = len(str(item))
                if length > widths[i]:
                    widths[i] = length
        template = " ".join(
            "{%s:%s%s}" % (i, (">" if i else "<"), w)
            for i, w in enumerate(widths)
        )

        def write(row):
            print(template.format(*row), file=output_file)
        return write

    if output_file != sys.stdout:
        output_file = open(output_file, "w", encoding='utf-8')
    if write_csv:
        writer = csv.writer(output_file, dialect="excel")
        write = writer.writerow
    else:
        def write(row):
            if row:
                if len(row) == 1 and not pending:
                    print(row[0], file=output_file)
                else:
                    pending.append(row)
            else:
                if pending:
                    write = make_row_widths_writer(pending, output_file)
                    for row in pending:
                        write(row)
                    del pending[:]
                print("", file=output_file)

    pending = []
    try:
        yield write
    finally:
        if pending:
            write([])
        assert not pending, pending
        if output_file != sys.stdout:
            output_file.close()


def sizeof_fmt(num):
    # copied/slightly modified from corehq.couchapps.dbaccessors
    if not num:
        return ''
    for x in ['B', 'KB', 'MB', 'GB', 'TB']:
        if num < 1024.0:
            return "%3.1f %s" % (num, x)
        num /= 1024.0
    return "%3.1f %s" % (num, 'PB')


## https://stackoverflow.com/a/27758326/10840
def mean(data):
    """Return the sample arithmetic mean of data."""
    n = len(data)
    if n < 1:
        raise ValueError('mean requires at least one data point')
    return sum(data) / n

#def _ss(data):
#    """Return sum of square deviations of sequence data."""
#    c = mean(data)
#    ss = sum((x-c) ** 2 for x in data)
#    return ss
#
#def stddev(data, ddof=0):
#    """Calculates the population standard deviation
#    by default; specify ddof=1 to compute the sample
#    standard deviation.
#    """
#    n = len(data)
#    if n < 2:
#        raise ValueError('variance requires at least two data points')
#    ss = _ss(data)
#    pvar = ss / (n - ddof)
#    return pvar ** 0.5
#
#
#def get_sample_size(population_size, samples, z_score=1.96, error_margin=0.05):
#    """Get sample size needed to calculate a meaningful mean
#
#    This function must be called multiple times to determine a suitable
#    meaningful sample size. For example, the first time it is called it
#    will return 100 or the population size, whichever is less. If the
#    population size is very large this will probably have little value.
#    Subsequent calls with the obtained samples should refine the result,
#    assuming the samples have a reasonably random distribution.
#
#    Sources:
#    https://www.surveymonkey.com/mp/sample-size-calculator/
#    https://en.wikipedia.org/wiki/Sample_size_determination
#    http://courses.wcupa.edu/rbove/Berenson/10th%20ed%20CD-ROM%20topics/section8_7.pdf
#
#    :param population_size: Total number of items being sampled.
#    :param samples: List of samples already obtained (may be empty).
#    :param z_score: Z-score for confidence level.
#    :param error_margin: Acceptable margin of error percentage expressed
#    as a decimal.
#    :returns: The number of samples needed for a meaninful mean.
#    """
#    return 100
#    # TODO implement this
#    if len(samples) < 100:
#        return min(100, population_size)
#    p = .1 + sqrt((ps * (1 - ps)) / len(samples))  # UNFINISHED: this doesn't work
#    z_num = z_score ** 2 * p * (1 - p)
#    e_sqr = error_margin ** 2
#    sample_size = (z_num / e_sqr) / (1 + (z_num / (e_sqr * population_size)))
#    return int(sample_size + 1)
