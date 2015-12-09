from collections import defaultdict
from optparse import make_option
from couchdbkit import Database

from django.core.management.base import BaseCommand
from corehq.preindex import get_preindex_plugins
from dimagi.utils.couch.database import get_design_docs


class Command(BaseCommand):
    help = 'Delete all unreferenced couch design docs.'

    option_list = BaseCommand.option_list + (
        make_option('--noinput', help='Do not prompt user for input', action='store_true',
                    default=False),
    )

    def handle(self, *args, **options):
        # build a data structure indexing databases to relevant design docs
        db_label_map = defaultdict(lambda: set())

        # pull design docs from preindex plugins
        plugins = get_preindex_plugins()
        for plugin in plugins:
            for design in plugin.get_designs():
                if design.design_path:
                    db_label_map[design.db.uri].add(design.app_label)

        designs_to_delete = {}
        for db_uri in db_label_map:
            db = Database(db_uri)
            expected_designs = db_label_map[db_uri]
            design_docs = get_design_docs(db)
            found_designs = set(dd.name for dd in design_docs)
            to_delete = found_designs - expected_designs
            if to_delete:
                designs_to_delete[db] = [ddoc._doc for ddoc in design_docs if ddoc.name in to_delete]
                print '\ndeleting from {}:\n---------------------'.format(db.dbname)
                print '\n'.join(sorted(to_delete))

        if designs_to_delete:
            if options['noinput'] or raw_input('\n'.join([
                    '\n\nReally delete all the above design docs?',
                    'If any of these views are actually live, bad things will happen. '
                    '(Type "delete designs" to continue):',
                    '',
            ])).lower() == 'delete designs':
                for db, design_docs in designs_to_delete.items():
                    for design_doc in design_docs:
                        # If we don't delete conflicts, then they take the place of the
                        # document when it's deleted. (That's how couch works.)
                        # This results in a huge reindex for an old conflicted version
                        # of a design doc we don't even want anymore.
                        delete_conflicts(db, design_doc['_id'])
                    db.delete_docs(design_docs)
            else:
                print 'aborted!'
        else:
            print 'database already completely pruned!'


class MyConflictsDontDie(Exception):
    pass


def delete_conflicts(db, doc_id):
    doc_with_conflicts = db.get(doc_id, conflicts=True)
    if '_conflicts' in doc_with_conflicts:
        conflict_revs = doc_with_conflicts['_conflicts']
        db.bulk_delete([{'_id': doc_id, '_rev': rev} for rev in conflict_revs])
        doc_with_conflicts = db.get(doc_id, conflicts=True)
        if '_conflicts' in doc_with_conflicts:
            raise MyConflictsDontDie(doc_with_conflicts)
