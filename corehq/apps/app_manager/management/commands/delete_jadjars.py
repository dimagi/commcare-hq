# Feel free to delete this file after March 2016
from django.core.management.base import BaseCommand
from django.template.defaultfilters import filesizeformat
from corehq.dbaccessors.couchapps.all_docs import (get_all_docs_with_doc_types,
                                                   get_doc_count_by_type)
from corehq.doctypemigrations.migrator_instances import apps_migration
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    help = "Display information about jad and jar files on applications"

    def handle(self, *args, **options):
        db = apps_migration.source_db
        docs = get_all_docs_with_doc_types(db, apps_migration.doc_types)
        total_size = sum(get_doc_count_by_type(db, doc_type)
                         for doc_type in apps_migration.doc_types)
        print "Searching {} documents".format(total_size)

        jar_count, jar_size = 0, 0
        jad_count, jad_size = 0, 0
        for doc in with_progress_bar(docs, length=total_size):
            if '_attachments' in doc:
                for filename, info in doc['_attachments'].items():
                    if filename == 'CommCare.jar':
                        jar_count += 1
                        jar_size += info['length']
                    elif filename == 'CommCare.jad':
                        jad_count += 1
                        jad_size += info['length']

        print u"Found {} jar files totaling {}".format(jar_count, filesizeformat(jar_size))
        print u"Found {} jad files totaling {}".format(jad_count, filesizeformat(jad_size))
