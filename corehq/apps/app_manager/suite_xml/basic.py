from abc import ABCMeta, abstractmethod
from corehq.apps.app_manager.suite_xml.contributors.careplan import CareplanContributor
from corehq.apps.app_manager.suite_xml.contributors.fixtures import FixtureContributor
from corehq.apps.app_manager.suite_xml.contributors.instances import EntryInstances
from corehq.apps.app_manager.suite_xml.contributors.menus import MenuContributor
from corehq.apps.app_manager.suite_xml.contributors.resources import FormResourceContributor, LocaleResourceContributor
from corehq.apps.app_manager.suite_xml.contributors.scheduler import SchedulerContributor
from corehq.apps.app_manager.suite_xml.contributors.workflow import WorkflowContributor
from corehq.apps.app_manager.suite_xml.xml import Suite


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
        getattr(self.suite, self.section).extend(getattr(self.get_section_contributions()))

    @abstractmethod
    def get_section_contributions(self):
        pass

class SuiteGeneratorBase(object):
    descriptor = None
    contributors = ()

    def __init__(self, app):
        self.app = app
        # this is actually so slow it's worth caching
        self.modules = list(self.app.get_modules())

    def generate_suite(self):
        suite = Suite(
            version=self.app.version,
            descriptor=self.descriptor,
        )

        def add_to_suite(Contributor):
            Contributor(suite, self.app, self.modules).contribute()

        map(add_to_suite, self.contributors)
        return suite.serializeDocument(pretty=True)


class SuiteGenerator(SuiteGeneratorBase):
    descriptor = u"Suite File"
    contributors = (
        # Basic sections
        FormResourceContributor,
        LocaleResourceContributor,
        MenuContributor,
        FixtureContributor,
        
        # Features
        CareplanContributor,
        SchedulerContributor,

        # Post process
        WorkflowContributor,
        EntryInstances,
    )

    def __init__(self, app):
        super(SuiteGenerator, self).__init__(app)
