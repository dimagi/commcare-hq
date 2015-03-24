import json
import requests
from collections import defaultdict
from django.core.management.base import LabelCommand
from jsonobject import JsonObject, StringProperty, ListProperty, base


class Command(LabelCommand):
    help = ("Run couch views on docs from different database instances."
            "See couch_integrity/basic.json for example config")
    label = "config file"

    def handle_label(self, *labels, **options):
        with open(labels[0]) as f:
            integrity_config = IntegrityConfig.wrap(json.loads(f.read()))
            integrity_check(integrity_config)


def integrity_check(config):
    for view in config.views:
        matches = defaultdict(list)
        for database in config.databases:
            params = {
                'reduce': 'false',
                'limit': 0
            }
            resp = requests.get("{database}/{view}".format(database=database.uri, view=view),
                                params=params,
                                headers=database.headers)

            content = json.loads(resp.content)
            matches[content['total_rows']].append(database.uri)

        print_result(matches, view)


def print_result(matches, view):
    if not matches:
        return

    print "##### {} #####".format(view)

    if len(matches) == 1:
        print u"All is consistent in each database for this view"
        return

    for rows, databases in matches.items():
        print u"Databases: "
        for db in databases:
            print db
        print u"Had this many {} rows for this view".format(rows)


class CouchDBConfig(JsonObject):
    uri = StringProperty()
    headers = base.DefaultProperty()


class IntegrityConfig(JsonObject):
    databases = ListProperty(CouchDBConfig)
    views = ListProperty()
