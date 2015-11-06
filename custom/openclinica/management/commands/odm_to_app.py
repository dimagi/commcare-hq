"""
Create a template app from ODM-formatted OpenClinica study metadata
"""
from lxml import etree
from django.core.management.base import BaseCommand
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application, Module, OpenCaseAction
from custom.openclinica.utils import odm_nsmap


# Map ODM data types to XForm data types
DATA_TYPES = {
    'text': 'string',
    'date': 'date',
    'integer': 'int',
    'time': 'time',
    'datetime': 'dateTime',
    'boolean': 'boolean',
    'float': 'decimal',
    'double': 'decimal',
}


class StudyObject(object):
    """
    Base class of objects defined from ODM metadata
    """
    def __init__(self, defn, meta):
        """
        Initialize

        :param defn: This object's definition
        :param meta: Study metadata
        """
        self.defn = defn
        self.meta = meta


class Study(StudyObject):

    def __init__(self, defn, meta):
        super(Study, self).__init__(defn, meta)
        self.oid = defn.get('OID')
        self.name = defn.xpath('./odm:GlobalVariables/odm:StudyName', namespaces=odm_nsmap)[0].text

    def iter_events(self):
        for se_ref in self.meta.xpath('./odm:Protocol/odm:StudyEventRef', namespaces=odm_nsmap):
            se_oid = se_ref.get('StudyEventOID')
            se_def = self.meta.xpath('./odm:StudyEventDef[@OID="{}"]'.format(se_oid), namespaces=odm_nsmap)[0]
            yield StudyEvent(se_def, self.meta)

    @staticmethod
    def new_subject_module():
        module = Module.new_module('Study Subjects', None)
        module.case_type = 'subject'
        reg_form = module.new_form('Register Subject')
        reg_form.actions.open_case = OpenCaseAction(name_path="/data/name", external_id=None)
        reg_form.actions.open_case.condition.type = 'always'
        return module

    def get_new_app(self, domain_name, app_name, version=APP_V2):
        app = Application.new_app(domain_name, app_name, application_version=version)
        app.name = self.name
        app.add_module(self.new_subject_module())
        for event in self.iter_events():
            module = event.get_new_module()
            for study_form in event.iter_forms():
                study_form.add_new_form_to_module(module)
            app.add_module(module)
        return app


class StudyEvent(StudyObject):

    def __init__(self, defn, meta):
        super(StudyEvent, self).__init__(defn, meta)
        self.oid = defn.get('OID')
        self.name = defn.get('Name')
        self.is_repeating = defn.get('Repeating') == 'Yes'
        self.event_type = defn.get('Type')  # Scheduled, Unscheduled, or Common

    def iter_forms(self):
        for form_ref in self.defn.xpath('./odm:FormRef', namespaces=odm_nsmap):
            form_oid = form_ref.get('FormOID')
            form_def = self.meta.xpath('./odm:FormDef[@OID="{}"]'.format(form_oid), namespaces=odm_nsmap)[0]
            yield StudyForm(form_def, self.meta)

    def get_new_module(self):
        """
        Return a CommCare module
        """
        module = Module.new_module(self.name, None)
        module.case_type = 'event'
        return module


class StudyForm(StudyObject):

    def __init__(self, defn, meta):
        super(StudyForm, self).__init__(defn, meta)
        self.oid = defn.get('OID')
        self.name = defn.get('Name')
        self.is_repeating = defn.get('Repeating') == 'Yes'

    def add_form_to_module(self, module):
        """
        Add a CommCare form based in this form's item groups and items to a given CommCare module
        """
        form = module.new_form(self.name, None)
        form.source = self.build_xform()

    def build_form(self):
        # TODO: Return xform source
        return ''


class Command(BaseCommand):
    help = 'Create an application from an ODM document in the given domain'
    args = '<domain> <app-name> <odm-doc>'

    def handle(self, *args, **options):
        domain_name, app_name, odm_filename = args
        study = self.get_study(odm_filename)
        app = study.get_new_app(domain_name, app_name)
        app.save()

    @staticmethod
    def get_study(odm_filename):
        with open(odm_filename) as odm_file:
            odm = etree.parse(odm_file)
        meta = odm.xpath('./odm:Study/odm:MetaDataVersion', namespaces=odm_nsmap)[0]
        study_def = odm.xpath('./odm:Study', namespaces=odm_nsmap)[0]
        return Study(study_def, meta)
