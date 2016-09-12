from __future__ import with_statement
import unittest
import os
import persistence
from setup import init_classpath
init_classpath()

CUR_DIR = os.path.dirname(__file__)


class SqlitePersistenceTest(unittest.TestCase):

    def test_sqlite_set(self):
        user = "test_user"
        persistence.postgres_set_sqlite(user, 1)
        date_one = persistence.postgres_lookup_sqlite_last_modified(user)
        persistence.postgres_set_sqlite(user, 2)
        date_two = persistence.postgres_lookup_sqlite_last_modified(user)
        version = persistence.postgres_lookup_sqlite_version(user)
        self.assertTrue(date_two > date_one)
        self.assertTrue(version == 2)

if __name__ == '__main__':
    unittest.main()
