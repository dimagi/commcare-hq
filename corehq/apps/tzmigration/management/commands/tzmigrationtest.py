import collections
from copy import deepcopy
import json
from django.core.management.base import LabelCommand
from couchdbkit import ResourceNotFound
import sqlite3
from casexml.apps.case.xform import get_case_updates
from corehq.apps.tzmigration import force_phone_timezones_should_be_processed
from corehq.apps.tzmigration.timezonemigration import json_diff
from corehq.util.dates import iso_string_to_datetime
from couchforms import convert_xform_to_json
from couchforms.models import XFormInstance
from couchforms.util import adjust_datetimes, scrub_meta
from dimagi.utils.couch.database import iter_docs
from couchforms.dbaccessors import get_form_ids_by_type


def is_datetime(string):
    if not isinstance(string, basestring):
        return False

    try:
        iso_string_to_datetime(string)
    except ValueError:
        return False
    else:
        return True


def get_submission_xml(xform_id):
    try:
        xml = XFormInstance.get_db().fetch_attachment(xform_id, 'form.xml')
    except ResourceNotFound:
        raise
    else:
        if isinstance(xml, unicode):
            xml = xml.encode('utf-8')
    return xml


def get_new_form_json(xml, xform_id):
    form_json = convert_xform_to_json(xml)
    with force_phone_timezones_should_be_processed():
        adjust_datetimes(form_json)
    # this is actually in-place because of how jsonobject works
    scrub_meta(XFormInstance.wrap({'form': form_json, '_id': xform_id}))
    return form_json


class CaseFormRelations(object):
    def __init__(self):
        self.connection = None

    def setup(self):
        self.connection = sqlite3.connect('example.db')
        cursor = self.connection.cursor()
        cursor.execute("""
          CREATE TABLE commcare_form(
            uuid text CONSTRAINT commcare_form_pk PRIMARY KEY,
            form_json text
          )
        """)
        cursor.execute("""
          CREATE TABLE commcare_case(
            uuid text CONSTRAINT commcare_case_pk PRIMARY KEY
          )
        """)
        cursor.execute("""
          CREATE TABLE commcare_case_action(
            commcare_form INTEGER,
            commcare_case INTEGER,
            action text,
            FOREIGN KEY(commcare_form) REFERENCES commcare_form(uuid),
            FOREIGN KEY(commcare_case) REFERENCES commcare_case(uuid)
          )
        """)
        self.connection.commit()

    def add_form(self, xform_id, form_json):
        cursor = self.connection.cursor()
        cursor.execute(
            'INSERT INTO commcare_form(uuid, form_json) VALUES (?, ?)',
            (xform_id, json.dumps(form_json))
        )
        self.connection.commit()

    def ensure_case(self, case_id):
        cursor = self.connection.cursor()
        cursor.execute(
            'INSERT OR IGNORE INTO commcare_case(uuid) VALUES (?)',
            (case_id,)
        )
        self.connection.commit()

    def add_case_actions(self, case_id, case_actions):
        cursor = self.connection.cursor()
        cursor.executemany(
            'INSERT INTO commcare_case_action(commcare_form, commcare_case, action) VALUES (?, ?, ?)',
            [(xform_id, case_id, json.dumps(case_actions)) for xform_id, case_actions in case_actions]
        )
        self.connection.commit()


class Command(LabelCommand):
    def handle_label(self, domain, **options):
        self.tzmigrationtest(domain)

    def tzmigrationtest(self, domain):
        case_form_relations = CaseFormRelations()
        case_form_relations.setup()
        xform_ids = get_form_ids_by_type(domain, 'XFormInstance')
        if not xform_ids:
            self.stderr('No XForms Found\n')
        diffs_by_xform_id = collections.defaultdict(list)

        for i, xform in enumerate(iter_docs(XFormInstance.get_db(), xform_ids)):
            xform_id = xform['_id']
            case_actions_by_case_id = collections.defaultdict(list)
            xml = get_submission_xml(xform_id)
            form_json = get_new_form_json(xml, xform_id)
            case_form_relations.add_form(xform_id, form_json)

            case_updates = get_case_updates(form_json)
            xform_copy = deepcopy(xform)
            xform_copy['form'] = form_json
            xformdoc = XFormInstance.wrap(xform_copy)

            case_actions = [
                (case_update.id, action.xform_id, action.to_json())
                for case_update in case_updates
                for action in case_update.get_case_actions(xformdoc)
            ]

            for case_id, xform_id, case_action in case_actions:
                case_actions_by_case_id[case_id].append((xform_id, case_action))

            for case_id, case_actions in case_actions_by_case_id.items():
                case_form_relations.ensure_case(case_id)
                case_form_relations.add_case_actions(case_id, case_actions)

            for type_, path, first, second in json_diff(xform['form'], form_json):

                diffs_by_xform_id[xform_id].append({
                    'type': type_,
                    'path': list(path),
                    'old': first,
                    'new': second
                })

            print {'xform_id': xform_id, 'diffs': diffs_by_xform_id[xform_id]}
