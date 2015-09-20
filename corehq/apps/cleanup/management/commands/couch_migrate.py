import json
from django.core.management.base import LabelCommand, CommandError
from optparse import make_option
from dimagi.ext.jsonobject import JsonObject, StringProperty, ListProperty
from corehq.apps.domain.models import Domain
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.bulk import get_docs
from dimagi.utils.couch.database import get_db


class Command(LabelCommand):
    help = "Run couch migrations of docs from one database to another"
    args = "config_file"
    label = "config file"

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

    def handle(self, *args, **options):
        if len(args) != 1:
            raise CommandError("Usage is ./manage.py couch_migrate [config_file]!")

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
    for domain in domain_names:
        for doc_type in config.doc_types:
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
                        if doc['_id'] in new_revs:
                            doc['_rev'] = new_revs[doc['_id']]
                    config.dest_db.bulk_save(docs)

            print 'copied {} {}s from {}'.format(len(ids_of_this_type), doc_type, domain)
    print 'copy docs complete'


def _replicate(config):
    result = config.source_db.server.replicate(
        config.source_db.uri,
        config.dest_db.uri,
        continuous=True,
        filter="hqadmin/domains_and_doc_types",
        query_params={'doc_types': ' '.join(config.doc_types)},
    )
    print 'started replication: {}'.format(result)


def _check(config):
    for view in config.couch_views:
        source_rows = config.source_db.view(view, limit=0, reduce=False).total_rows
        dest_rows = config.dest_db.view(view, limit=0, reduce=False).total_rows
        if source_rows == dest_rows:
            print 'WOOT! {} looks good: {} rows in both databases'.format(view, source_rows)
        else:
            print 'SHUCKS... {} has different data: {} rows in source db and {} in dest'.format(
                view, source_rows, dest_rows
            )
    print 'check complete'


class MigrationConfig(JsonObject):
    from_db_postfix = StringProperty()
    to_db_postfix = StringProperty()
    doc_types = ListProperty(required=True)
    couch_views = ListProperty()

    @property
    def source_db(self):
        return get_db(self.from_db_postfix)

    @property
    def dest_db(self):
        return get_db(self.to_db_postfix)
