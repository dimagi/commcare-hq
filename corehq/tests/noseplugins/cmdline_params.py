"""
A plugin to accept parameters used for various test runner operations.
"""
from nose.plugins import Plugin


class CmdLineParametersPlugin(Plugin):
    """Accept and store misc test runner flags for later reference
    """
    name = "cmdline-parameters"
    enabled = True
    parameters = {}

    def options(self, parser, env):
        reuse_msg = " To be used in conjunction with REUSE_DB=1."
        parser.add_option(
            '--reset-db',
            action="store_true",
            default=False,
            help=("Drop existing test dbs, then create and migrate new ones, but do not teardown "
                  "after running tests. This is convenient when the existing databases are "
                  "outdated and need to be rebuilt." + reuse_msg),
        )
        parser.add_option(
            '--flush-db',
            action="store_true",
            default=False,
            help=("Flush all objects from the old test databases before running tests.  Much "
                  "faster than `--reset-db`." + reuse_msg),
        )
        parser.add_option(
            '--migrate-db',
            action="store_true",
            default=False,
            help="Migrate the test databases before running tests." + reuse_msg,
        )
        parser.add_option(
            '--teardown-db',
            action="store_true",
            default=False,
            help="Skip database setup; do normal teardown after running tests." + reuse_msg,
        )
        parser.add_option(
            "--collect-only",
            action="store_true",
            default=False,
        )

    def configure(self, options, conf):
        db_action = None
        for action in ['reset_db', 'flush_db', 'migrate_db', 'teardown_db']:
            if getattr(options, action):
                db_action = action
        type(self).parameters['db_action'] = db_action
        type(self).parameters['collect_only'] = options.collect_only

    @classmethod
    def get(cls, parameter):
        return cls.parameters[parameter]
