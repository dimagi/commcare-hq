from datetime import datetime
from django.core.management import call_command
from django.test import TestCase

from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.management.commands.migrate_caserepeater import \
    Command as MigrationCommand
from corehq.motech.repeaters.models import CaseRepeater, SQLCaseRepeater


class TestMigrationDiff(TestCase):

    @classmethod
    def setUpClass(cls):
        domain = 'caserepeater-migration'
        cls.conn = ConnectionSettings(domain=domain, url='http://url.com')
        cls.conn.save()
        cls.couch_repeater_obj = CaseRepeater(
            _id='id_1',
            domain=domain,
            connection_settings_id=cls.conn.id,
            white_listed_case_types=['white_case', 'black_case'],
            black_listed_users=['user1'],
            paused=False,
            format='case_json',
        )
        cls.sql_repeater_obj = SQLCaseRepeater(
            domain=domain,
            connection_settings=cls.conn,
            white_listed_case_types=['white_case', 'black_case'],
            black_listed_users=['user1'],
            is_paused=False,
            format='case_json',
            repeater_id='id_1',
        )
        cls.incorrect_sql_repeater_obj = SQLCaseRepeater(
            domain=domain,
            connection_settings=cls.conn,
            white_listed_case_types=['black_case'],
            black_listed_users=['user2'],
            is_paused=True,
            format='case_json',
            repeater_id='id_1',
        )
        super().setUpClass()

    def test_diff_couch_and_sql_with_no_diff(self):
        output = MigrationCommand.diff_couch_and_sql(self.couch_repeater_obj.to_json(), self.sql_repeater_obj)
        self.assertIsNone(output)

    def test_diff_couch_and_sql_with_diff(self):
        output = MigrationCommand.diff_couch_and_sql(
            self.couch_repeater_obj.to_json(),
            self.incorrect_sql_repeater_obj
        )

        self.assertEqual(output, [
            "paused: couch value False != sql value True",
            "white_listed_case_types: 2 in couch != 1 in sql",
            "black_listed_users: couch value 'user1' != sql value 'user2'"
        ])


class TestMigrationCommand(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain_1 = 'caserepeater-migration'
        cls.domain_2 = 'migration-caserepeater'
        cls.date = datetime.utcnow().strftime('%Y-%m-%dT%H-%M-%S')
        cls.conn = ConnectionSettings(domain=cls.domain_1, url='http://url.com')
        cls.conn.save()
        cls.couch_repeater_1 = CaseRepeater(
            domain=cls.domain_1,
            connection_settings_id=cls.conn.id,
            format='case_json',
        )
        cls.couch_repeater_2 = CaseRepeater(
            domain=cls.domain_2,
            connection_settings_id=cls.conn.id,
            format='case_json',
        )
        cls.couch_repeater_3 = CaseRepeater(
            domain=cls.domain_1,
            connection_settings_id=cls.conn.id,
            format='case_json',
        )
        cls.repeaters = [cls.couch_repeater_1, cls.couch_repeater_2, cls.couch_repeater_3]

        for repeater in cls.repeaters:
            repeater.save(sync_to_sql=False)
        return super(TestMigrationCommand, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        for r in cls.repeaters:
            r.delete()
        return super().tearDownClass()

    def test_migration_with_no_arguments(self):
        self.assertEqual(SQLCaseRepeater.objects.count(), 0)
        # when multiple tests run in the same second they try to create log file with same name
        # so we have to pass custom log_path to avoid test failure because of it
        call_command('migrate_caserepeater', log_path=f'caserepeater_noargs_{self.date}.log')
        self.assertEqual(SQLCaseRepeater.objects.count(), len(self.repeaters))
        sql_repeater_ids = SQLCaseRepeater.objects.all().values_list('repeater_id', flat=True)
        couch_repeater_ids = [r._id for r in self.repeaters]
        self.assertListEqual(sorted(sql_repeater_ids), sorted(couch_repeater_ids))

    def test_migration_for_one_domain(self):
        self.assertEqual(SQLCaseRepeater.objects.count(), 0)
        call_command(
            'migrate_caserepeater',
            domains=[self.domain_1],
            log_path=f'caserepeater_one_domain_{self.date}.log'
        )
        self.assertEqual(SQLCaseRepeater.objects.count(), 2)
        self.assertEqual(
            list(SQLCaseRepeater.objects.all().values_list('domain', flat=True).distinct()),
            [self.domain_1]
        )
        # running migration twice to verify nothing unexpected happens
        call_command(
            'migrate_caserepeater',
            domains=[self.domain_1],
            log_path=f'caserepeater_onedomain_{self.date}.log'
        )
        self.assertEqual(SQLCaseRepeater.objects.count(), 2)
        self.assertEqual(
            list(SQLCaseRepeater.objects.all().values_list('domain', flat=True).distinct()),
            [self.domain_1]
        )
