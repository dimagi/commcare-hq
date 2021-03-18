from django.test import TestCase
from testil import eq

from corehq.apps.hqwebapp.models import UserAccessLog, UserAgent

from .. models import ForeignValue


def test_foreign_value_class_attribute():
    prop = UserAccessLog.user_agent
    assert isinstance(prop, ForeignValue), prop


def test_foreign_value_default_is_none():
    eq(UserAccessLog().user_agent, None)


def test_get_foreign_value():
    log = UserAccessLog(user_agent_fk=UserAgent(value="Mozilla"))
    eq(log.user_agent, "Mozilla")
    eq(log.user_agent_fk.id, None)
    eq(log.user_agent_fk_id, None)


def test_foreign_value_names():
    class Base:
        f0 = ForeignValue(None)

    class Sub1(Base):
        f1 = ForeignValue(None)

    class Sub2(Base):
        f2 = ForeignValue(None)

    eq(ForeignValue.get_names(Base), ["f0"])
    eq(ForeignValue.get_names(Sub1), ["f0", "f1"])
    eq(ForeignValue.get_names(Sub2), ["f0", "f2"])


class TestForeignValue(TestCase):

    def setUp(self):
        self.log = UserAccessLog()

    def tearDown(self):
        UserAccessLog.user_agent.get_related.cache_clear()

    def test_set_foreign_value(self):
        self.log.user_agent = "Mozilla"
        self.assertEqual(self.log.user_agent_fk.value, "Mozilla")
        self.assertIsNotNone(self.log.user_agent_fk_id)

    def test_set_foreign_value_to_none(self):
        self.log.user_agent = "Mozilla"
        self.log.user_agent = None
        self.assertEqual(self.log.user_agent_fk, None)
        self.assertEqual(self.log.user_agent_fk_id, None)

    def test_set_and_truncate_foreign_value(self):
        self.log.user_agent = "*" * UserAgent.MAX_LENGTH * 2
        self.assertEqual(self.log.user_agent_fk.value, "*" * UserAgent.MAX_LENGTH)

    def test_foreign_value_init(self):
        log = UserAccessLog(user_agent="Mozilla")
        self.assertEqual(log.user_agent_fk.value, "Mozilla")

    def test_get_foreign_value_after_save(self):
        self.log.user_agent = "Mozilla"
        self.log.save()
        log2 = UserAccessLog.objects.get(id=self.log.id)
        self.assertIsNot(self.log, log2)
        self.assertEqual(log2.user_agent, "Mozilla")

    def test_reuse_foreign_value(self):
        self.log.user_agent = "Mozilla"
        self.log.save()
        log2 = UserAccessLog(user_agent="Mozilla")
        log2.save()
        self.assertNotEqual(self.log.id, log2.id)
        self.assertEqual(self.log.user_agent_fk_id, log2.user_agent_fk_id)

    def test_lru_cache(self):
        info = UserAccessLog.user_agent.get_related.cache_info()
        self.assertEqual(info.misses, 0)
        self.assertEqual(info.hits, 0)

        self.log.user_agent = "Mozilla"
        info = UserAccessLog.user_agent.get_related.cache_info()
        self.assertEqual(info.misses, 1)
        self.assertEqual(info.hits, 0)

        UserAccessLog(user_agent="Mozilla")
        info = UserAccessLog.user_agent.get_related.cache_info()
        self.assertEqual(info.misses, 1)
        self.assertEqual(info.hits, 1)
