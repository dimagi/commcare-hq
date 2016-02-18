"""
Feel free to delete this file after March 2016

Local: 1052 Application docs and 890MB of jar files
Staging: 4743 Application docs and 4GB of jar files
Prod: 118414 Application docs, so likely ~100GB of jar files

Deletion took about 5 minutes locally, so we're looking at ~10 hours on prod
"""
import sys
from optparse import make_option
from couchdbkit.exceptions import ResourceConflict
from dimagi.utils.decorators.memoized import memoized
from django.core.management.base import BaseCommand
from django.template.defaultfilters import filesizeformat
from corehq.dbaccessors.couchapps.all_docs import (get_all_docs_with_doc_types,
                                                   get_doc_count_by_type)
from corehq.doctypemigrations.migrator_instances import apps_migration
from corehq.util.log import with_progress_bar
from corehq.apps.app_manager.models import Application


class Command(BaseCommand):
    help = ("Display information about jad and jar files on applications.  "
            "Pass in either --stats or --delete.")
    option_list = BaseCommand.option_list + (
        make_option('--stats',
                    action='store_true',
                    dest='stats',
                    help='Show stats about the files to be deleted.'),
        make_option('--delete',
                    action='store_true',
                    dest='delete',
                    help='Delete all jad and jar files from Applications.'),
    )

    def handle(self, *args, **options):
        if not (options['stats'] or options['delete']):
            print self.help
            sys.exit()

        if options['stats']:
            self.show_info()
        elif options['delete']:
            self.delete_jadjars()

    @property
    @memoized
    def docs_count(self):
        return sum(get_doc_count_by_type(Application.get_db(), doc_type)
                   for doc_type in apps_migration.doc_types)

    def iter_attachments(self):
        docs = get_all_docs_with_doc_types(Application.get_db(),
                                           apps_migration.doc_types)
        for doc in with_progress_bar(docs, length=self.docs_count):
            if '_attachments' in doc:
                for filename, info in doc['_attachments'].items():
                    yield doc, filename, info

    def show_info(self):
        print "Searching {} documents".format(self.docs_count)
        jar_count, jar_size = 0, 0
        jad_count, jad_size = 0, 0
        for doc, filename, info in self.iter_attachments():
            if filename == 'CommCare.jar':
                jar_count += 1
                jar_size += info['length']
            elif filename == 'CommCare.jad':
                jad_count += 1
                jad_size += info['length']
        print u"Found {} jar files totaling {}".format(jar_count, filesizeformat(jar_size))
        print u"Found {} jad files totaling {}".format(jad_count, filesizeformat(jad_size))

    def delete_jadjars(self):
        if raw_input("Are you sure you want to delete the attachments from {} "
                     "docs?\n(y/n)".format(self.docs_count)) != "y":
            sys.exit()

        db = Application.get_db()
        count_deleted, size_deleted, failures = 0, 0, 0
        for doc, filename, info in self.iter_attachments():
            if filename in ['CommCare.jar', 'CommCare.jad']:
                try:
                    db.delete_attachment(doc, filename)
                except ResourceConflict:
                    failures += 1
                else:
                    count_deleted += 1
                    size_deleted += info['length']

        print (u"Deleted {} attachments, totalling {}."
               .format(count_deleted, filesizeformat(size_deleted)))
        if failures:
            print "{} failures, please run command again".format(failures)
