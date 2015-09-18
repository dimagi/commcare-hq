from abc import ABCMeta, abstractmethod


class SuiteContributor(object):
    __metaclass__ = ABCMeta

    def __init__(self, suite, app, modules):
        self.suite = suite
        self.app = app
        self.modules = modules

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
