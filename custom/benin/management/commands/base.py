import itertools
import sqlite3


class Updater(object):
    chunk_size = 100  # Could potentially increase this
    batch_size = 20000  # Maximum number of cases to process in a single script run
    stat_counts = {
        'success': 0,
        'skipped': 0,
        'failed': 0,
    }

    def __init__(self, domain, db_manager):
        self.db_manager = db_manager
        self.domain = domain


class DBManager(object):
    STATUS_PENDING = 'pending'
    STATUS_SUCCESS = 'success'
    STATUS_FAILURE = 'failure'
    STATUS_SKIPPED = 'skipped'

    VALID_STATUS = [
        STATUS_PENDING,
        STATUS_SUCCESS,
        STATUS_FAILURE,
        STATUS_SKIPPED,
    ]

    def __init__(self, db_file_path, table_name):
        self.db_file_path = db_file_path
        self.table_name = table_name

    def _get_db_cur(self):
        con = sqlite3.connect(self.db_file_path)
        return con.cursor()

    def setup_db(self):
        cur = self._get_db_cur()
        cur.execute(f"CREATE TABLE {self.table_name} (id, revert_id, status, message)")
        cur.connection.commit()
        cur.close()

    def create_row(self, id):
        # TODO: Catch status that's not pending?
        cur = self._get_db_cur()
        cur.execute(f"INSERT INTO {self.table_name} VALUES (?, ?, ?, ?)", (id, '', self.STATUS_PENDING, ''))
        cur.connection.commit()
        cur.close()

    def get_ids(self, count: int = None):
        cur = self._get_db_cur()
        res = cur.execute(
            "SELECT id FROM {} WHERE status IN ('{}', '{}')".format(
                self.table_name, self.STATUS_PENDING, self.STATUS_FAILURE
            )
        )
        if count:
            ids = res.fetchmany(count)
        else:
            ids = res.fetchall()
        cur.close()
        flattened_ids = list(itertools.chain.from_iterable(ids))
        return flattened_ids

    def update_row(self, id, value_dict):
        """
        value_dict: Has the following format:
        {
            'col_name': 'col_val',
            ...
        }
        Valid column names are revert_id, status, message
        """
        query = f'UPDATE {self.table_name} SET '
        expr_list = []
        for key, val in value_dict.items():
            expr = f"{key} = '{val}'"
            expr_list.append(expr)
        query += ', '.join(expr_list)

        cur = self._get_db_cur()
        cur.execute(f'{query} WHERE id = ?', (id,))
        cur.connection.commit()
        cur.close()
