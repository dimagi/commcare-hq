from abc import ABCMeta, abstractmethod


class BaseSuiteContributor(object):
    __metaclass__ = ABCMeta

    def __init__(self, suite, app, modules):
        from corehq.apps.app_manager.suite_xml.entries import EntriesHelper
        self.suite = suite
        self.app = app
        self.modules = modules
        self.entries_helper = EntriesHelper(app, modules)


class SuiteContributor(BaseSuiteContributor):
    __metaclass__ = ABCMeta

    @abstractmethod
    def contribute(self):
        pass


class SectionSuiteContributor(SuiteContributor):
    __metaclass__ = ABCMeta
    section = None

    def contribute(self):
        suite_section = getattr(self.suite, self.section)
        section_contributions = self.get_section_contributions()
        suite_section.extend(section_contributions)

    @abstractmethod
    def get_section_contributions(self):
        pass


class SuiteContributorByModule(BaseSuiteContributor):
    __metaclass__ = ABCMeta
    section = None

    @abstractmethod
    def get_module_contributions(self, module):
        return []
