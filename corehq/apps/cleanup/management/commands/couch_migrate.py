import json
from datetime import datetime
from optparse import make_option

from django.core.management.base import LabelCommand, CommandError
from dimagi.ext.jsonobject import JsonObject, StringProperty, ListProperty
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.bulk import get_docs
from dimagi.utils.couch.database import get_db

from corehq import Domain
from corehq.apps.userreports.filters.factory import FilterFactory
from corehq.apps.domainsync.config import DocumentTransform, save


class Command(LabelCommand):
    help = "Run couch migrations of docs from one database to another"
    args = "config_file"
    label = "config file"
    pillow_class = None  # Specify a pillow class to save the sequence_id
    file_prefix = "couch_migrate_"

    option_list = LabelCommand.option_list + (
        make_option('--replicate',
                    action='store_true',
                    dest='replicate',
                    default=False,
                    help="Replicate documents."),
        make_option('--copy',
                    action='store_true',
                    dest='copy',
                    default=False,
                    help="Copy documents manually, by view."),
        make_option('--check',
                    action='store_true',
                    dest='check',
                    default=False,
                    help="Check views."),
    )

    def get_seq_filename(self):
        datestring = datetime.utcnow().strftime("%Y-%m-%d-%H%M")
        seq_filename = "{}{}_{}_seq.txt".format(self.file_prefix, self.pillow_class.__name__, datestring)
        return seq_filename

    def handle(self, *args, **options):
        if len(args) != 1:
            raise CommandError("Usage is ./manage.py couch_migrate [config_file]!")

        if self.pillow_class:
            self.pillow = self.pillow_class()
            seq_id = self.pillow.couch_db.info()['update_seq']
            # Write sequence file to disk
            seq_filename = self.get_seq_filename()
            log('Writing sequence file to disk: {}'.format(seq_filename))
            with open(seq_filename, 'w') as f:
                f.write(str(seq_id))

        file_path = args[0]
        with open(file_path) as f:
            migration_config = MigrationConfig.wrap(json.loads(f.read()))
            if options['replicate']:
                _replicate(migration_config)
            if options['copy']:
                _copy(migration_config)
            if options['check']:
                _check(migration_config)


def _copy(config):
    # unfortunately the only couch view we have for this needs to go by domain
    # will be a bit slow
    database = Domain.get_db()
    assert database.uri == config.source_db.uri, 'can only use "copy" with the main HQ DB as the source'
    domain_names = Domain.get_all_names()
    filter_ = None
    if config.filters:
        filter_ = FilterFactory.from_spec(
            {
                'type': 'and',
                'filters': config.filters
            }
        )
    for domain in domain_names:
        for doc_type in config.doc_types:
            copied = 0
            ids_of_this_type = [row['id'] for row in database.view(
                'domain/docs',
                startkey=[domain, doc_type],
                endkey=[domain, doc_type, {}],
                reduce=False,
                include_docs=False,
            )]
            if ids_of_this_type:
                new_revs = dict([
                    (row['id'], row['value']['rev'])
                    for row in config.dest_db.view('_all_docs', keys=ids_of_this_type, include_docs=False)
                    if 'error' not in row
                ])
                for id_group in chunked(ids_of_this_type, 500):
                    docs = get_docs(database, id_group)
                    for doc in docs:
                        if filter_ and not filter_(doc):
                            continue
                        if doc['_id'] in new_revs:
                            doc['_rev'] = new_revs[doc['_id']]
                        dt = DocumentTransform(doc, database)
                        save(dt, config.dest_db)
                        copied += 1

            log('copied {} {}s from {}'.format(copied, doc_type, domain))
    log('copy docs complete')


def _replicate(config):
    result = config.source_db.server.replicate(
        config.source_db.uri,
        config.dest_db.uri,
        continuous=True,
        filter="hqadmin/domains_and_doc_types",
        query_params={'doc_types': ' '.join(config.doc_types)},
    )
    log('started replication: {}'.format(result))


def _check(config):
    for view in config.couch_views:
        source_rows = config.source_db.view(view, limit=0, reduce=False).total_rows
        dest_rows = config.dest_db.view(view, limit=0, reduce=False).total_rows
        if source_rows == dest_rows:
            log('WOOT! {} looks good: {} rows in both databases'.format(view, source_rows))
        else:
            log('SHUCKS... {} has different data: {} rows in source db and {} in dest'.format(
                view, source_rows, dest_rows
            ))
    log('check complete')


def log(message):
    print '[{}] {}'.format(__name__.split('.')[-1], message)


class MigrationConfig(JsonObject):
    from_db_postfix = StringProperty()
    to_db_postfix = StringProperty()
    doc_types = ListProperty(required=True)
    couch_views = ListProperty()
    filters = ListProperty()

    @property
    def source_db(self):
        return get_db(self.from_db_postfix)

    @property
    def dest_db(self):
        return get_db(self.to_db_postfix)
