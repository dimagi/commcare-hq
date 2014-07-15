from optparse import make_option
import alembic
from django.core.management.base import BaseCommand
from django.conf import settings
import sh
from sqlalchemy.engine import create_engine
from sqlalchemy.orm.session import sessionmaker
import sys
from ctable.models import SqlExtractMapping
from dimagi.utils.decorators.memoized import memoized
from pillowtop.utils import import_pillow_string
from scripts.sh_verbose import ShVerbose
import os
from os.path import expanduser

home = expanduser("~")

class Command(BaseCommand):
    help = 'Migrate reporting data (ctable + fluff) from reporting database to main database'

    option_list = BaseCommand.option_list + (
        make_option('--dry-run', action='store_true',  default=False,
                    help="Don't actually do anything"),
    )

    def handle(self, *args, **options):
        verbose = int(options.get('verbosity', 1)) > 1
        dry_run = options.get('dry_run', False)

        if dry_run:
            print "\n-------- DRY RUN --------\n"

        old_db = settings.SQL_REPORTING_DATABASE_URL.split('/')[-1]
        if '?' in old_db:
            old_db = old_db.split('?')[0]

        db_settings = settings.DATABASES["default"].copy()
        db_settings['PORT'] = db_settings.get('PORT', None) or '5432'
        maindb_url = "postgresql://{USER}:{PASSWORD}@{HOST}:{PORT}/{NAME}".format(
            **db_settings
        )

        pgpass_file = self.write_pgpass(db_settings, old_db)

        report_tables = self.get_db_tables(settings.SQL_REPORTING_DATABASE_URL)
        ctable_tables = self.get_ctable_tables()
        fluff_tables = self.get_fluff_tables()
        main_tables = self.get_db_tables(maindb_url)
        for old, new in (ctable_tables | fluff_tables):
            if not old in report_tables:
                print "* '%s' expected table not found" % old
            else:
                report_tables.remove(old)

                if new in main_tables:
                    print "- '%s' already migrated" % old
                    continue
                elif not old in main_tables:
                    print "+ '%s' migrating" % old
                    old_quoted = '\"%s\"' % old  # quotes required for tables with not all lowercase names
                    if not dry_run:
                        self.migrate_table(db_settings, old_db, old_quoted, verbose)

                if new != old:
                    self.rename_table(maindb_url, old, new, dry_run=dry_run)

        for session in self.session.get_cache(self).values():
            session.close()

        os.remove(pgpass_file)

        if report_tables:
            print "\nSome tables not migrated:"
            for r in report_tables:
                print "    %s" % r

    def migrate_table(self, db_settings, old_db, old_table, verbose):
        with ShVerbose(verbose=verbose):
            sh.psql(
                sh.pg_dump(old_db, h=db_settings['HOST'], p=db_settings['PORT'], U=db_settings['USER'], t=old_table,
                           _piped=True),
                db_settings['NAME'],
                h=db_settings['HOST'],
                p=db_settings['PORT'],
                U=db_settings['USER'])

    def rename_table(self, db_url, old, new, dry_run=False):
        print "+ '%s' renaming to '%s'" % (old, new)
        if not dry_run:
            session = self.session(db_url)
            op = self.op(session.connection())
            op.rename_table(old, new)
            session.commit()

    @memoized
    def op(self, connection):
        ctx = alembic.migration.MigrationContext.configure(connection)
        return alembic.operations.Operations(ctx)

    def get_ctable_tables(self):
        prefix = 0
        if hasattr(settings, 'CTABLE_PREFIX'):
            prefix = len(settings.CTABLE_PREFIX) + 1
        else:
            cont = raw_input("No CTABLE_PREFIX setting. Do you want to continue (yes/no): ")
            if cont != 'yes':
                sys.exit(1)

        return {(m.table_name[prefix:], m.table_name)
            for m in SqlExtractMapping.view('ctable/by_name', include_docs=True)}

    def get_fluff_tables(self):
        fluff_pillows = [import_pillow_string(x) for x in settings.PILLOWTOPS['fluff']]
        tables = set()
        for pillow in fluff_pillows:
            if pillow.save_direct_to_sql:
                name = pillow.indicator_class()._table.name
                tables.add((name, name))
        return tables


    def get_db_tables(self, database_url):
        session = self.session(database_url)
        results = session.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public';
            """)

        return [r[0] for r in results]

    @memoized
    def session(self, url):
        engine = create_engine(url)
        session = sessionmaker(bind=engine)
        return session()

    def write_pgpass(self, db_settings, old_db):
        pgpass = []
        for db in [db_settings['NAME'], old_db]:
            pgpass.append("{0}:{1}:{2}:{3}:{4}".format(
                db_settings['HOST'],
                db_settings['PORT'],
                db,
                db_settings['USER'],
                db_settings['PASSWORD'],
            ))
        pgpass_file = '{0}/.pgpass'.format(home)
        with open(pgpass_file, 'w') as f:
            f.write('\n'.join(pgpass))

        sh.chmod('0600', pgpass_file)
        return pgpass_file
