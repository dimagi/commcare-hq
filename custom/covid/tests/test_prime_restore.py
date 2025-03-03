from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.test import TestCase

from casexml.apps.phone.models import SyncLogSQL
from corehq.apps.domain.auth import FORMPLAYER
from custom.formplayer.restore_priming import get_users_for_priming


def make_synclog(domain, date, user, request_user=None, is_formplayer=True, case_count=None, auth_type=None):
    return SyncLogSQL(
        domain=domain, user_id=user, request_user_id=request_user, is_formplayer=is_formplayer, date=date,
        case_count=case_count, auth_type=auth_type, doc={}
    )


class PrimeRestoreTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.window_start = datetime.utcnow() - relativedelta(hours=5)
        cls.cutoff = datetime.utcnow() - relativedelta(hours=2)

        before_window = datetime.utcnow() - relativedelta(hours=6)
        in_window = datetime.utcnow() - relativedelta(hours=4)
        after_cutoff = datetime.utcnow() - relativedelta(hours=1)
        SyncLogSQL.objects.bulk_create([
            make_synclog(domain="d1", user="u1", request_user=None, is_formplayer=True, date=before_window),
            make_synclog(domain="d1", user="u1", request_user=None, is_formplayer=True, date=in_window,
                         case_count=100),
            make_synclog(domain="d1", user="u1", request_user="u2", is_formplayer=True, date=in_window,
                         case_count=100),
            make_synclog(domain="d1", user="u3", request_user=None, is_formplayer=True, date=in_window,
                         case_count=10),
            make_synclog(domain="d1", user="u4", request_user="u5", is_formplayer=True, date=after_cutoff),
            # not formplayer
            make_synclog(domain="d1", user="u4", is_formplayer=False, date=in_window),
            # formplayer auth
            make_synclog(domain="d1", user="u4", is_formplayer=True, date=in_window, auth_type=FORMPLAYER),
            # different domain
            make_synclog(domain="d2", user="u6", request_user=None, is_formplayer=True, date=in_window),
        ])

    @classmethod
    def tearDownClass(cls):
        SyncLogSQL.objects.all().delete()
        super().tearDownClass()

    def test_get_users_for_priming(self):
        users = set(get_users_for_priming("d1", self.window_start, self.cutoff))
        self.assertEqual({(None, "u1"), ("u2", "u1"), (None, "u3")}, users)

    def test_get_users_for_priming_case_count(self):
        users = set(get_users_for_priming("d1", self.window_start, self.cutoff, min_case_load=50))
        self.assertEqual({(None, "u1"), ("u2", "u1")}, users)
