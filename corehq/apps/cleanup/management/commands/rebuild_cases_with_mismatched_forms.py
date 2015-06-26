import logging
from optparse import make_option
from django.core.management.base import BaseCommand, LabelCommand
from casexml.apps.case.cleanup import rebuild_case
from couchlog.models import ExceptionRecord
from dimagi.utils.couch.pagination import LucenePaginator
from django.conf import settings

SEARCH_VIEW_NAME = getattr(settings, "COUCHLOG_LUCENE_VIEW", "couchlog/search")


def get_records_to_process(search_key, batch_size):
    def wrapper(row):
        id = row["id"]
        doc = ExceptionRecord.get(id)
        domain = doc.domain if hasattr(doc, "domain") else ""
        try:
            domain, case_id = domain.split(',')
        except ValueError:
            return {'exception': doc}
        return {
            'domain': domain,
            'case_id': case_id,
            'exception': doc
        }

    search_key = "%s AND NOT archived" % search_key

    paginator = LucenePaginator(SEARCH_VIEW_NAME, wrapper, database=ExceptionRecord.get_db())
    return paginator.get_results(search_key, batch_size, 0)


class Command(BaseCommand):
    help = ('Rebuild cases that have been identified to have mismatched forms and actions.'
            'See http://manage.dimagi.com/default.asp?158779 for details.')

    option_list = LabelCommand.option_list + (
        make_option(
            '--limit',
            action='store',
            type='int',
            dest='limit',
            default=1000,
            help="Only reprocess this many cases."),
        make_option(
            '--batch-size',
            action='store',
            type='int',
            dest='batch',
            default=100,
            help="Size of batches to process"),
        make_option(
            '-q',
            action='store_true',
            dest='quiet',
            default=False,
            help="Don't print output"),
    )

    def handle(self, *args, **options):
        count = 1
        limit, batch, quiet = options['limit'], options['batch'], options['quiet']
        while True:
            if not quiet:
                print 'Fetching new batch'
            total, records = get_records_to_process('CASE XFORM MISMATCH', batch)
            if not quiet:
                print 'Records in batch:', total
            if not total:
                return
            for record in records:
                if 'case_id' not in record:
                    record['exception'].archive('system')
                    continue
                case_id = record['case_id']
                try:
                    rebuild_case(case_id)
                    record['exception'].archive('system')
                    if not quiet:
                        print 'rebuilt %s/%s cases' % (count, total)
                except Exception, e:
                    logging.exception("couldn't rebuild case {id}. {msg}".format(id=case_id, msg=str(e)))
                finally:
                    count += 1
                    if count > limit:
                        return
