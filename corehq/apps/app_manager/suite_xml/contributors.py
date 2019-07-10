from __future__ import absolute_import
from abc import ABCMeta, abstractmethod, abstractproperty
import six


class BaseSuiteContributor(six.with_metaclass(ABCMeta, object)):
    def __init__(self, suite, app, modules, build_profile_id=None):
        from corehq.apps.app_manager.suite_xml.sections.entries import EntriesHelper
        self.suite = suite
        self.app = app
        self.modules = modules
        self.build_profile_id = build_profile_id
        self.entries_helper = EntriesHelper(app, modules, build_profile_id=self.build_profile_id)


class SectionContributor(six.with_metaclass(ABCMeta, BaseSuiteContributor)):
    @abstractproperty
    def section_name(self):
        pass

    @abstractmethod
    def get_section_elements(self):
        return []


class SuiteContributorByModule(six.with_metaclass(ABCMeta, BaseSuiteContributor)):
    section = None

    @abstractmethod
    def get_module_contributions(self, module):
        return []


class PostProcessor(six.with_metaclass(ABCMeta, BaseSuiteContributor)):
    @abstractmethod
    def update_suite(self):
        pass
