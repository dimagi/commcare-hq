from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import (
    PopulateSQLCommand,
)


class Command(PopulateSQLCommand):
    @classmethod
    def couch_db_slug(cls):
        return None

    @classmethod
    def couch_doc_type(self):
        return 'CommCareBuild'

    @classmethod
    def sql_class(self):
        from corehq.apps.builds.models import CommCareMobileBuild

        return CommCareMobileBuild

    @classmethod
    def commit_adding_migration(cls):
        return 'TODO: add once the PR adding this file is merged'

    @classmethod
    def diff_couch_and_sql(cls, couch, sql):
        diffs = []
        for attr in [
            'build_number',
            'version',
            'time',
        ]:
            diff = cls.diff_attr(attr, couch, sql)
            if diff:
                diffs.append(diff)
        return '\n'.join(diffs) if diffs else None
