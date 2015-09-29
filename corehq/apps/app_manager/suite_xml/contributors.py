from abc import ABCMeta, abstractmethod, abstractproperty


class BaseSuiteContributor(object):
    __metaclass__ = ABCMeta

    def __init__(self, suite, app, modules):
        from corehq.apps.app_manager.suite_xml.sections.entries import EntriesHelper
        self.suite = suite
        self.app = app
        self.modules = modules
        self.entries_helper = EntriesHelper(app, modules)


class SectionContributor(BaseSuiteContributor):
    __metaclass__ = ABCMeta

    @abstractproperty
    def section_name(self):
        pass

    @abstractmethod
    def get_section_elements(self):
        return []


class SuiteContributorByModule(BaseSuiteContributor):
    __metaclass__ = ABCMeta
    section = None

    @abstractmethod
    def get_module_contributions(self, module):
        return []


class PostProcessor(BaseSuiteContributor):
    __metaclass__ = ABCMeta

    @abstractmethod
    def update_suite(self):
        pass
