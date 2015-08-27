import sqlite3
import json


class PlanningDB(object):
    def __init__(self, db_filepath):
        self.db_filepath = db_filepath
        self._connection = None

    @classmethod
    def init(cls, db_filepath):
        self = cls(db_filepath)
        self.setup()
        return self

    @classmethod
    def open(cls, db_filepath):
        return cls(db_filepath)

    @property
    def connection(self):
        if not self._connection:
            self._connection = sqlite3.connect(self.db_filepath)
        return self._connection

    def setup(self):
        cursor = self.connection.cursor()
        cursor.execute("""
          CREATE TABLE commcare_form(
            uuid text CONSTRAINT commcare_form_pk PRIMARY KEY,
            form_json text
          )
        """)
        cursor.execute("""
          CREATE TABLE commcare_form_diff(
            commcare_form text,
            diff_type text,
            path text,
            old_value text,
            new_value text,
            FOREIGN KEY(commcare_form) REFERENCES commcare_form(uuid)
          )
        """)
        cursor.execute("""
          CREATE TABLE commcare_case(
            uuid text CONSTRAINT commcare_case_pk PRIMARY KEY
          )
        """)
        cursor.execute("""
          CREATE TABLE commcare_case_action(
            commcare_form text,
            commcare_case text,
            action text,
            FOREIGN KEY(commcare_form) REFERENCES commcare_form(uuid),
            FOREIGN KEY(commcare_case) REFERENCES commcare_case(uuid)
          )
        """)
        self.connection.commit()

    def add_form(self, form_id, form_json):
        cursor = self.connection.cursor()
        cursor.execute(
            'INSERT INTO commcare_form(uuid, form_json) VALUES (?, ?)',
            (form_id, json.dumps(form_json))
        )

    def add_form_diffs(self, form_id, form_diffs):
        cursor = self.connection.cursor()

        def json_dumps_or_none(val):
            if val is Ellipsis:
                return None
            else:
                return json.dumps(val)

        cursor.executemany("""
            INSERT INTO commcare_form_diff(
                commcare_form, diff_type, path, old_value, new_value)
              VALUES (?, ?, ?, ?, ?)
        """, [(form_id, d.diff_type, json.dumps(d.path),
               json_dumps_or_none(d.old_value),
               json_dumps_or_none(d.new_value))
              for d in form_diffs]
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

    def get_all_form_ids(self):
        cursor = self.connection.cursor()
        form_ids = {uuid for (uuid,) in
                    cursor.execute('SELECT uuid FROM commcare_form')}
        return form_ids

    def get_all_case_ids(self):
        cursor = self.connection.cursor()
        case_ids = {uuid for (uuid,) in
                    cursor.execute('SELECT uuid FROM commcare_case')}
        return case_ids

    def get_form_ids_by_cases(self, case_ids):
        cursor = self.connection.cursor()
        set_fragment = ','.join(['?'] * len(case_ids))
        return {form_id for (form_id, _) in cursor.execute("""
            SELECT commcare_form, commcare_case
              FROM commcare_case_action
              WHERE commcare_case IN ({})
            """.format(set_fragment), tuple(case_ids),
        )}

    def get_case_ids_by_forms(self, form_ids):
        cursor = self.connection.cursor()
        set_fragment = ','.join(['?'] * len(form_ids))
        return {case_id for (_, case_id) in cursor.execute("""
            SELECT commcare_form, commcare_case
              FROM commcare_case_action
              WHERE commcare_form IN ({})
            """.format(set_fragment), tuple(form_ids),
        )}

    def span_form_id(self, form_id):
        form_ids = {form_id}
        case_ids = set()
        new_forms = {form_id}
        new_cases = set()
        while new_forms or new_cases:
            new_cases = self.get_case_ids_by_forms(form_ids) - case_ids
            case_ids |= new_cases
            new_forms = self.get_form_ids_by_cases(case_ids) - form_ids
            form_ids |= new_forms
        return form_ids, case_ids

    def get_form_diffs(self):
        from corehq.apps.tzmigration.timezonemigration import FormJsonDiff
        cursor = self.connection.cursor()

        def json_loads_or_ellipsis(val):
            if val is None:
                return Ellipsis
            else:
                return json.loads(val)

        for commcare_form, diff_type, path, old_value, new_value in cursor.execute("""
          SELECT commcare_form, diff_type, path, old_value, new_value
          FROM commcare_form_diff
        """):
            yield commcare_form, FormJsonDiff(
                diff_type, json.loads(path), json_loads_or_ellipsis(old_value),
                json_loads_or_ellipsis(new_value))
