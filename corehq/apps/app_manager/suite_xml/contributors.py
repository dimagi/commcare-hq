from builtins import object
from abc import ABCMeta, abstractmethod, abstractproperty
from future.utils import with_metaclass


class BaseSuiteContributor(with_metaclass(ABCMeta, object)):
    def __init__(self, suite, app, modules):
        from corehq.apps.app_manager.suite_xml.sections.entries import EntriesHelper
        self.suite = suite
        self.app = app
        self.modules = modules
        self.entries_helper = EntriesHelper(app, modules)


class SectionContributor(with_metaclass(ABCMeta, BaseSuiteContributor)):
    @abstractproperty
    def section_name(self):
        pass

    @abstractmethod
    def get_section_elements(self):
        return []


class SuiteContributorByModule(with_metaclass(ABCMeta, BaseSuiteContributor)):
    section = None

    @abstractmethod
    def get_module_contributions(self, module):
        return []


class PostProcessor(with_metaclass(ABCMeta, BaseSuiteContributor)):
    @abstractmethod
    def update_suite(self):
        pass
