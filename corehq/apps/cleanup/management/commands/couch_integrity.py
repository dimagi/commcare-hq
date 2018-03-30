from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import json
import requests
from collections import defaultdict
from django.core.management.base import BaseCommand
from django.conf import settings
from dimagi.ext.jsonobject import JsonObject, StringProperty, ListProperty
from jsonobject.base import DefaultProperty

# This command relies on a properly formatted json spec in order to run.
# Here is an example of a spec:
#
# {
#     "couches": [ // Couches defines the couchdb configuration you want.
#         {
#             "host": "commcarehq.cloudant.com",
#             "user": "<username>", // optional, falls back to your `settings.py` file for the apprioriate user
#             "password": "<password>", // optional, falls back to your `settings.py` file for apprioriate user
#             "headers": {} // Optional headers to pass into the request to couch
#         }
#
#     ],
#     "suites": [ // suites defines what views you'd like to run on your couch environments
#         {
#             "database": "commcarehq" // choose a database to run the view on
#             "views": [ // list of views to run on the database
#                 "_all_docs"
#             ]
#         }
#
#     ]
# }
#
# When no user or password is supplied, this command will fallback to the `settings.py`
# file to look for the user and password. An example user defined in the `settings.py` file would look like
# this:
#
# CI_COMMCAREHQ_CLOUDANT_COM_USER = 'commcarehq'
#
# A few things are happening here. First, you must prefix the variable with CI_. Next you have to enter the
# host name. Since you cannot declare variables with '.' in them, use '_' instead. Lastly, you need to add the
# suffix _USER or _PASSWORD so the command knows whether you are defining the user or the password.
# A complete example:
#
# CI_COMMCAREHQ_CLOUDANT_COM_USER = 'commcarehq'
# CI_COMMCAREHQ_CLOUDANT_COM_PASSWORD = '***'
#
# CI_DIMAGI003_CLOUDANT_COM_USER = 'commcarehq'
# CI_DIMAGI003_CLOUDANT_COM_PASSWORD = '***'


class Command(BaseCommand):
    help = ("Run couch views on docs from different database instances."
            "See couch_integrity/basic.json for example config")
    label = "config file"

    def add_arguments(self, parser):
        parser.add_argument(
            'filename',
        )
        parser.add_argument(
            '--wiggle',
            dest='wiggle',
            default=0,
            type=int,
            help='Define how much doc counts can be off by',
        )


    def handle_label(self, filename, **options):
        wiggle = options['wiggle']
        with open(filename) as f:
            integrity_config = IntegrityConfig.wrap(json.loads(f.read()))
            integrity_check(integrity_config, wiggle)


def integrity_check(config, wiggle=0):
    for suite in config.suites:
        for view in suite.views:
            matches = defaultdict(list)
            for couch in config.couches:
                params = {
                    'reduce': 'false',
                    'limit': 0
                }
                resp = requests.get("{uri}/{database}/{view}".format(uri=couch.uri,
                                                                    database=suite.database,
                                                                    view=view),
                    params=params,
                    headers=couch.headers)

                content = json.loads(resp.content)
                try:
                    total_rows = content['total_rows']
                except KeyError:
                    print("Problem getting `total_rows`. Is this a valid couch database?  {}"\
                        .format(suite.database))
                else:
                    matched = False
                    for wiggle_range, couches in matches.items():
                        if wiggle_range[0] <= total_rows <= wiggle_range[1]:
                            matches[wiggle_range].append((couch.uri, total_rows))
                            matched = True

                    if not matched:
                        new_wiggle_range = (total_rows - wiggle, total_rows + wiggle)
                        matches[new_wiggle_range].append((couch.uri, total_rows))

            print_result(matches, view, suite.database)


def print_result(matches, view, database):
    if not matches:
        return

    if len(matches) == 1:
        print("{}All is consistent in {} for view {}{}".format(Colors.OKGREEN, database, view, Colors.ENDC))
        return

    print("{}{} - {}{}".format(Colors.WARNING, database, view, Colors.ENDC))
    for wiggle_range, match_tuples in matches.items():
        print("Couches for wiggle range {}: ".format(wiggle_range))
        for couch_uri, rows in match_tuples:
            print("\t{}".format(couch_uri))
            print("\tHad this many {}{}{} rows for this view".format(
                Colors.BOLD,
                rows,
                Colors.ENDC))


class CouchConfig(JsonObject):
    user = StringProperty()
    password = StringProperty()
    host = StringProperty(required=True)
    headers = DefaultProperty()

    def __init__(self, obj=None, **kwargs):
        PREFIX = "CI"

        # Default to settings variables
        if 'user' not in obj:
            obj['user'] = getattr(settings, "{prefix}_{host}_USER".format(
                prefix=PREFIX,
                host=obj['host'].replace('.', '_').upper(),
            ))

        if 'password' not in obj:
            obj['password'] = getattr(settings, "{prefix}_{host}_PASSWORD".format(
                prefix=PREFIX,
                host=obj['host'].replace('.', '_').upper(),
            ))

        super(CouchConfig, self).__init__(obj, **kwargs)

    @property
    def uri(self):
        return "https://{user}:{password}@{host}".format(
            user=self.user,
            password=self.password,
            host=self.host
        )


class SuiteConfig(JsonObject):
    database = StringProperty()
    views = ListProperty()


class IntegrityConfig(JsonObject):
    suites = ListProperty(SuiteConfig)
    couches = ListProperty(CouchConfig)


class Colors(object):
    # http://stackoverflow.com/a/287944/835696
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
