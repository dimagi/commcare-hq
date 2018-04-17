from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
from collections import namedtuple
from couchdbkit import ResourceNotFound
from django.core.management.base import BaseCommand
from dimagi.utils.chunked import chunked
from corehq.util.couch import send_keys_to_couch, IterDB
from corehq.util.couchdb_management import couch_config
from six.moves import input

Results = namedtuple('Results', ['restored', 'not_found', 'not_deleted'])


def get_deleted_doc(db, doc_id, rev):
    res = db.get(doc_id, revs=True, rev=rev)
    start = res['_revisions']['start']
    ids = res['_revisions']['ids']
    prev_revision = "{}-{}".format(start-1, ids[1])
    try:
        doc = db.get(doc_id, rev=prev_revision)
    except ResourceNotFound:
        res.pop('_deleted')
        res.pop('_revisions')
        doc = res
    doc.pop('_rev')
    return doc


def undelete_docs(db, doc_ids):
    results = Results(set(), set(), set())
    with IterDB(db) as iter_db:
        for chunk in chunked(set(doc_ids), 100):
            for res in send_keys_to_couch(db, keys=set(chunk)):
                doc_id = res['key']
                if res.get('error', None) == 'not_found':
                    results.not_found.add(doc_id)
                elif res.get('value', {}).get('deleted', False):
                    iter_db.save(
                        get_deleted_doc(db, doc_id, res['value']['rev'])
                    )
                    results.restored.add(doc_id)
                else:
                    results.not_deleted.add(doc_id)
    return results, iter_db


class Command(BaseCommand):
    help = ("Accepts a series of deleted document ids from stdin and "
            "restores them to the revision immediately prior to deletion."
            "\nUsage: './manage.py undelete_docs [database] [ids_file]'")

    def add_arguments(self, parser):
        parser.add_argument('database')
        parser.add_argument('ids_file')

    def handle(self, database, ids_file, **options):
        # figure out db to use
        slugs = ['commcarehq'] + sorted([_f for _f in couch_config.all_dbs_by_slug if _f])
        if database not in slugs:
            print ("Did not recognize a database called '{}'.  "
                   "Options are: {}".format(database, ", ".join(slugs)))
            return
        slug = None if database == 'commcarehq' else database
        db = couch_config.all_dbs_by_slug[slug]

        # get list of doc_ids
        try:
            with open(ids_file) as f:
                doc_ids = [doc_id.strip() for doc_id in f.readlines()]
        except IOError:
            print("Couldn't find a file called '{}'".format(ids_file))
            return

        # confirm
        msg = ("Are you sure you want to undelete {} docs from {}? (y/n)\n"
               .format(len(doc_ids), db.dbname))
        if input(msg) != "y":
            return

        # actually do the work
        results, iter_db = undelete_docs(db, doc_ids)

        # Now, what happened?
        print("Restored {} docs".format(len(results.restored)))
        print("Didn't find {} ids".format(len(results.not_found)))
        print("{} docs weren't deleted".format(len(results.not_deleted)))

        outfile = "delete_from_{}_{}.txt".format(iter_db.db.dbname, datetime.now())
        with open(outfile, 'w') as f:
            f.write('\n'.join(get_output_file(results, iter_db)))
        print("Full results can be found in {}".format(outfile))


def get_output_file(results, iter_db):
    output = ["Deleting docs from {} on {}"
              .format(iter_db.db.dbname, datetime.now())]

    def write_section(header, ids):
        output.append("\n{}".format(header))
        output.extend(ids)

    write_section("RESTORED", results.restored)
    write_section("NOT FOUND", results.not_found)
    write_section("NOT DELETED", results.not_deleted)

    output.append("\n\nRESULTS FROM ITERDB")
    write_section("SAVED IDS", iter_db.saved_ids)
    write_section("DELETED IDS", iter_db.deleted_ids)
    write_section("ERROR IDS", iter_db.error_ids)
    return output
