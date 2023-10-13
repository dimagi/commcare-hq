"""A test timing plugin for nose

Usage: ./manage.py test --with-elasticsnitch --snitch-out=/path/to/elasticsnitch.txt
"""
import sys

from nose.plugins import Plugin
from corehq.tests.noseplugins.uniformresult import uniform_description
from corehq.apps.es.client import manager


class ElasticSnitchPlugin(Plugin):
    """A plugin to snitch on tests that change (add or delete) Elasticsearch
    indexes without cleaning up after themselves (putting the index "state"
    back how they found it).
    """

    name = "elasticsnitch"

    def options(self, parser, env):
        """Register commandline options."""
        super().options(parser, env)
        parser.add_option("--snitch-out", action="store", metavar="FILE",
                          help="Snitch output file (default: STDOUT)")

    def configure(self, options, conf):
        """Configure plugin."""
        super().configure(options, conf)
        self.conf = conf
        self.snitch_out = options.snitch_out
        self.prefix = "" if self.snitch_out else f"{self.name}: "

    def begin(self):
        self.output = (open(self.snitch_out, "w", encoding="utf-8")
                       if self.snitch_out else sys.__stdout__)

    def finalize(self, result):
        if self.output is not None and self.output is not sys.__stdout__:
            self.output.close()

    def startTest(self, case):
        """Make a record of existing index names.

        Called prior to test run:
        - after ``case.setUpClass()``
        - before ``case.setUp()``
        """
        self.start_indexes = get_all_index_names()

    def stopTest(self, case):
        """Compare existing index names against pre-test ones. If there are
        differences, write the delta.

        Called on test completion:
        - after: case.tearDown()
        - before: case.tearDownClass()
        """
        name = uniform_description(case.test)
        end_indexes = get_all_index_names()
        if not end_indexes ^ self.start_indexes:  # XOR
            return
        added = end_indexes - self.start_indexes
        removed = self.start_indexes - end_indexes
        self.output.write(f"{self.prefix}{name}: +{sorted(added)}, -{sorted(removed)}\n")


def get_all_index_names():
    """Returns a set of all existing Elasticsearch index names."""
    return set(manager.get_indices())
