from importlib import import_module
from unittest import TestCase

purge_platform_pkgs = import_module("scripts.purge-platform-pkgs")


class TestPurgePlatformPkgs(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.unwanted = {"dep": "parent"}

    def test_purge_packages(self):
        lines = self._make_lines("dep", "parent")
        self.assertEqual([], self._list_purged(lines, self.unwanted))

    def test_purge_packages_tolerates_empty(self):
        self.assertEqual([], self._list_purged([], self.unwanted))

    def test_purge_packages_ignores_others(self):
        lines = self._make_lines("django", "-r base.in")
        self.assertEqual(lines, self._list_purged(lines, self.unwanted))

    def test_purge_packages_ignores_near_match(self):
        lines = self._make_lines("dep", "parent-sub")
        self.assertEqual(lines, self._list_purged(lines, self.unwanted))

    def test_purge_packages_ignores_wrong_via(self):
        lines = self._make_lines("dep", "django")
        self.assertEqual(lines, self._list_purged(lines, self.unwanted))

    def test_purge_packages_ignores_multi_vias(self):
        lines = [
            "dep==1.2.3\n",
            "    # via\n",
            "    #   parent\n",
            "    #   django\n",
        ]
        self.assertEqual(lines, self._list_purged(lines, self.unwanted))

    def test_purge_packages_succeeds_as_first_package(self):
        expected = self._make_lines("django", "-r base.in")
        lines = self._make_lines("dep", "parent") + expected
        self.assertEqual(expected, self._list_purged(lines, self.unwanted))

    def test_purge_packages_succeeds_as_last_package(self):
        expected = self._make_lines("django", "-r base.in")
        lines = expected + self._make_lines("dep", "parent")
        self.assertEqual(expected, self._list_purged(lines, self.unwanted))

    @staticmethod
    def _list_purged(*args, **kw):
        return list(purge_platform_pkgs.purge_packages(*args, **kw))

    @staticmethod
    def _make_lines(name, via):
        return [
            f"{name}==1.2.3\n",
            f"    # via {via}\n",
        ]
