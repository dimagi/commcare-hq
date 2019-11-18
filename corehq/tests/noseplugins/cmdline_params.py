"""
A plugin to accept parameters used for various test runner operations.
"""
from nose.plugins import Plugin

REUSE_DB_HELP = """
To be used in conjunction with the environment variable REUSE_DB=1.
reset: Drop existing test dbs, then create and migrate new ones, but do not
    teardown after running tests. This is convenient when the existing databases
    are outdated and need to be rebuilt.
flush: Flush all objects from the old test databases before running tests.
    Much faster than `reset`.
migrate: Migrate the test databases before running tests.
teardown: Skip database setup; do normal teardown after running tests.
"""


class CmdLineParametersPlugin(Plugin):
    """Accept and store misc test runner flags for later reference
    """
    name = "cmdline-parameters"
    enabled = True
    parameters = {}

    def options(self, parser, env):
        parser.add_option(
            '--reusedb',
            default=None,
            choices=['reset', 'flush', 'migrate', 'teardown'],
            help=REUSE_DB_HELP,
        )
        # --collect-only is a built-in option, adding it here causes a warning

    def configure(self, options, conf):
        for option in ['reusedb', 'collect_only']:
            type(self).parameters[option] = getattr(options, option)

    @classmethod
    def get(cls, parameter):
        return cls.parameters[parameter]
