from contextlib import contextmanager
from unittest.mock import patch

from django.test import TestCase
from testil import eq

from corehq.apps.hqwebapp.models import UserAccessLog, UserAgent
from corehq.motech.repeaters.models import Repeater, ConnectionSettings

from .. models import ForeignObject, ForeignValue


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

        log2 = UserAccessLog(user_agent="Mozilla")
        info = UserAccessLog.user_agent.get_related.cache_info()
        self.assertEqual(info.misses, 1)
        self.assertEqual(info.hits, 1)

        # matching instances indicates LRU cache was used
        self.assertIs(self.log.user_agent_fk, log2.user_agent_fk)

    def test_get_value(self):
        self.log.user_agent = "Mozilla"
        self.log.save()

        UserAccessLog.user_agent.get_value.cache_clear()
        info = UserAccessLog.user_agent.get_value.cache_info()
        self.assertEqual(info.misses, 0)
        self.assertEqual(info.hits, 0)

        log = UserAccessLog.objects.get(id=self.log.id)
        self.assertEqual(log.user_agent, "Mozilla")
        info = UserAccessLog.user_agent.get_value.cache_info()
        self.assertEqual(info.misses, 1)
        self.assertEqual(info.hits, 0)

        log = UserAccessLog.objects.get(id=self.log.id)
        self.assertEqual(log.user_agent, "Mozilla")
        info = UserAccessLog.user_agent.get_value.cache_info()
        self.assertEqual(info.misses, 1)
        self.assertEqual(info.hits, 1)

    def test_foreign_value_duplicate(self):
        ua1 = UserAgent(value="Mozilla")
        ua2 = UserAgent(value="Mozilla")
        ua1.save()
        ua2.save()
        self.assertNotEqual(ua1.id, ua2.id)
        self.log.user_agent = "Mozilla"
        self.log.save()
        self.assertEqual(self.log.user_agent_fk.id, ua1.id)

    def test_get_related_lru_cache_disabled(self):
        with foreign_value_lru_cache_disabled("get_related"):
            self.log.user_agent = "Mozilla"
            log2 = UserAccessLog(user_agent="Mozilla")
            self.assertEqual(self.log.user_agent_fk.id, log2.user_agent_fk.id)

            # different instances indicates LRU cache was not used
            self.assertIsNot(self.log.user_agent_fk, log2.user_agent_fk)

    def test_get_value_lru_cache_disabled(self):
        with foreign_value_lru_cache_disabled("get_value"):
            self.log.user_agent = "Mozilla"
            self.log.save()
            log2 = UserAccessLog(user_agent="Mozilla")
            with self.assertNumQueries(1):
                self.assertEqual(log2.user_agent, "Mozilla")

            # successive access to the save value hits the DB
            log2 = UserAccessLog(user_agent="Mozilla")
            with self.assertNumQueries(1):
                self.assertEqual(log2.user_agent, "Mozilla")


@contextmanager
def foreign_value_lru_cache_disabled(cached_func):
    def reset_cached_property():
        fv_prop.__dict__.pop(cached_func, None)

    fv_prop = UserAccessLog.user_agent
    reset_cached_property()
    try:
        with patch.object(fv_prop, "cache_size", 0):
            yield
    finally:
        reset_cached_property()


def test_foreign_object_names():
    class Base:
        f0 = ForeignObject(None, None)

    class Sub1(Base):
        f1 = ForeignObject(None, None)

    class Sub2(Base):
        f2 = ForeignObject(None, None)

    eq(ForeignObject.get_names(Base), ["f0"])
    eq(ForeignObject.get_names(Sub1), ["f0", "f1"])
    eq(ForeignObject.get_names(Sub2), ["f0", "f2"])


def test_foreign_object_class_attribute():
    prop = Repeater.connection_settings
    assert isinstance(prop, ForeignObject), prop


def test_foreign_object_init():
    # not a method of TestForeignObject because this test should not hit the database
    cs = ConnectionSettings(id=42)
    obj = Repeater(connection_settings=cs)
    assert obj.connection_settings is cs, (obj.connection_settings, cs)
    eq(obj.connection_settings_id, 42)


def test_set_foreign_object():
    # not a method of TestForeignObject because this test should not hit the database
    obj = Repeater()
    obj.connection_settings = cs = ConnectionSettings(id=42)
    assert obj.connection_settings is cs, (obj.connection_settings, cs)
    eq(obj.connection_settings_id, 42)


class TestForeignObject(TestCase):

    def setUp(self):
        self.obj = Repeater()

    def test_foreign_object_default_does_not_exist(self):
        with self.assertRaises(ConnectionSettings.DoesNotExist):
            Repeater().connection_settings

    def test_set_foreign_object_to_none(self):
        self.obj.connection_settings = ConnectionSettings(id=42)
        self.obj.connection_settings = None
        with self.assertRaises(ConnectionSettings.DoesNotExist):
            self.obj.connection_settings
        self.assertEqual(self.obj.connection_settings_id, None)

    def test_get_foreign_object_after_save(self):
        cs = ConnectionSettings(id=42)
        cs.save()
        self.obj.connection_settings = cs
        self.obj.save()
        obj2 = Repeater.objects.get(id=self.obj.id)
        self.assertIsNot(self.obj, obj2)
        self.assertIsNot(obj2.connection_settings, cs)
        self.assertEqual(obj2.connection_settings.id, 42)

    def test_get_foreign_object_after_set_id_field(self):
        self.obj.connection_settings = ConnectionSettings(id=42)
        cs = ConnectionSettings(id=84)
        cs.save()
        self.obj.connection_settings_id = 84
        self.assertEqual(self.obj.connection_settings.id, cs.id)
        self.assertEqual(self.obj.connection_settings_id, 84)

    def test_get_foreign_object_after_set_id_field_to_none(self):
        self.obj.connection_settings = ConnectionSettings(id=42)
        cs = ConnectionSettings(id=84)
        cs.save()
        self.obj.connection_settings_id = None
        with self.assertRaises(ConnectionSettings.DoesNotExist):
            self.obj.connection_settings
        self.assertEqual(self.obj.connection_settings_id, None)

    def test_delete_foreign_object(self):
        self.obj.connection_settings = ConnectionSettings(id=42)
        del self.obj.connection_settings
        with self.assertRaises(ConnectionSettings.DoesNotExist):
            self.obj.connection_settings
        self.assertEqual(self.obj.connection_settings_id, None)

        with self.assertRaises(AttributeError):
            del self.obj.connection_settings
