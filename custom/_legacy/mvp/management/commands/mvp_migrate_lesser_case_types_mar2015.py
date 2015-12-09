import json
import datetime
from optparse import make_option
from couchdbkit import BulkSaveError
from corehq.apps.hqcase.dbaccessors import get_case_ids_in_domain
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.database import iter_docs, iter_bulk_delete
from django.core.management.base import LabelCommand, BaseCommand
from mvp.models import MVP
from casexml.apps.case.models import CommCareCase
from mvp_docs.models import IndicatorCase


class Command(LabelCommand):
    help = """
    Copy all cases of the specified case types from the main db
    to the indicator db with no changes.
    (If a doc with the same ID already exists in the indicator db,
    it will not be overwritten; this command will skip it.)

    During the original move in Feb 2015 of MVP indicators to a separate db,
    we forgot to also migrate case types that had no indicators associated.

    This is important because MPV couch views still reference those cases,
    even if no additional indicators are saved into them.
    """
    args = ""
    label = ""

    option_list = BaseCommand.option_list + (
        make_option('--domains', type='string', default=','.join(MVP.DOMAINS),
                    dest='domains',
                    action='store',
                    help='Domains to search for cases to copy'),
        make_option('--case_types', type='string',
                    dest='case_types',
                    action='store',
                    default='CHW,household,post_natal,verbal_autopsy',
                    help='Domains to search for cases to copy'),
        make_option('--chunk_size',
                    action='store',
                    type='int',
                    dest='chunk_size',
                    default=100,
                    help='Previous run input file prefix',)
    )

    def handle(self, *args, **options):
        chunk_size = options.get('chunk_size')
        domains = options.get('domains').split(',')
        case_types = options.get('case_types').split(',')
        self.handle_all(domains, case_types, chunk_size)

    def log(self, string):
        timestamp = datetime.datetime.utcnow().replace(microsecond=0)
        print "[{}] {}".format(timestamp, string)

    def handle_all(self, domains, case_types, chunk_size):
        for domain in domains:
            for case_type in case_types:
                self.handle_one(domain, case_type, chunk_size)

    def handle_one(self, domain, case_type, chunk_size):
        self.log('Copying {case_type} cases in {domain}'
                 .format(case_type=case_type, domain=domain))
        old_db = CommCareCase.get_db()
        new_db = IndicatorCase.get_db()
        assert old_db.uri != new_db.uri
        # this dbaccessor pulls from old_db
        case_ids = get_case_ids_in_domain(domain, case_type)
        self.delete_bad_doc_types(case_ids, chunk_size)
        case_dict_chunks = chunked(iter_docs(old_db, case_ids, chunk_size),
                                   chunk_size)

        for case_dicts in case_dict_chunks:
            for case_dict in case_dicts:
                del case_dict['_rev']
                case_dict.pop('_attachments', None)
                case_dict['doc_type'] = "IndicatorCase"
            try:
                results = new_db.bulk_save(case_dicts)
            except BulkSaveError as error:
                results = error.results
            for result in results:
                if result.get('error') == 'conflict':
                    self.log('- OK: [{id}] is already in the indicator db'
                             .format(id=result.get('id')))
                elif 'error' in result:
                    self.log('- ERROR: [{id}] ({result})'.format(
                        id=result.get('id'),
                        result=json.dumps(result)
                    ))
                else:
                    self.log('- ADDED: [{id}] saved to indicator db'.format(
                        id=result.get('id')
                    ))

    def delete_bad_doc_types(self, case_ids, chunk_size):
        """
        No view in this db includes CommCareCases, so check manually
        """
        db = IndicatorCase.get_db()
        case_dict_chunks = chunked(iter_docs(db, case_ids, chunk_size),
                                   chunk_size)
        to_delete = []
        for case_dicts in case_dict_chunks:
            for case_dict in case_dicts:
                if case_dict['doc_type'] == 'CommCareCase':
                    to_delete.append(case_dict['_id'])
                elif case_dict['doc_type'] != 'IndicatorCase':
                    raise Exception("Unexpected case type {} found"
                                    .format(case_dict['doc_type']))

        assert db.uri != CommCareCase.get_db().uri
        print "Deleting {} docs from db '{}'".format(len(to_delete), db.dbname)
        iter_bulk_delete(db, to_delete, chunk_size)
