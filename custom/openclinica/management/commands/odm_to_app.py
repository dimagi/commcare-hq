"""
Create a template app from ODM-formatted OpenClinica study metadata
"""
from lxml import etree
from django.core.management.base import BaseCommand
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import (
    Application,
    Module,
    OpenCaseAction,
    UpdateCaseAction,
    PreloadAction,
    OpenSubCaseAction,
    FormActionCondition,
)
from corehq.apps.app_manager.xform_builder import XFormBuilder
from custom.openclinica.utils import odm_nsmap
from dimagi.utils import make_uuid


# Map ODM data types to ODK XForm data types
# cf. http://www.cdisc.org/system/files/all/generic/application/octet-stream/odm1_3_0_final.htm#ItemDef
#     https://opendatakit.github.io/odk-xform-spec/#data-types
#     http://www.w3.org/TR/xmlschema-2/#built-in-primitive-datatypes
ODK_DATA_TYPES = {
    'text': 'string',
    'integer': 'int',
    'float': 'decimal',
    'date': 'date',
    'time': 'time',
    'datetime': 'dateTime',
    'string': 'string',
    'boolean': 'boolean',
    'double': 'decimal',
    'hexBinary': 'string',
    'base64Binary': 'string',
    'hexFloat': 'string',
    'base64Float': 'string',
    'partialDate': 'date',
    'partialTime': 'time',
    'partialDatetime': 'dateTime',
    'durationDatetime': 'string',
    'intervalDatetime': 'string',
    'incompleteDatetime': 'string',
    'URI': 'string',
    # Convert ODM questions with choices to XForm selects
    'select': 'select',
    'select1': 'select1',
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
    def get_subject_form_source(name):
        """
        Return a registration form that mimics OpenClinica subject registration
        """
        xform = XFormBuilder(name)
        xform.new_question('name', 'Person ID')  # Subject's unique ID. aka "Screening Number", "Subject Key"
        xform.new_question('subject_study_id', 'Subject Study ID')  # Subject number for this study
        xform.new_question('dob', 'Date of Birth', data_type='date')
        xform.new_question('sex', 'Sex', data_type='select1', choices={1: 'Male', 2: 'Female'})
        xform.new_question('enrollment_date', 'Enrollment Date', data_type='date')
        return xform.tostring(pretty_print=True)

    def new_subject_module(self, app):
        module = app.add_module(Module.new_module('Study Subjects', None))
        module.unique_id = 'study_subjects'
        module.case_type = 'subject'

        reg_form = module.new_form('Register Subject', None)
        reg_form.unique_id = make_uuid()
        reg_form.source = self.get_subject_form_source('Register Subject')
        reg_form.actions.open_case = OpenCaseAction(name_path='/data/name', external_id=None)
        reg_form.actions.open_case.condition.type = 'always'
        reg_form.actions.update_case = UpdateCaseAction(update={
            'subject_study_id': '/data/subject_study_id',
            'dob': '/data/dob',
            'sex': '/data/sex',
            'enrollment_date': '/data/enrollment_date',
        })
        reg_form.actions.update_case.condition.type = 'always'

        edit_form = module.new_form('Edit Subject', None)
        edit_form.unique_id = make_uuid()
        edit_form.source = self.get_subject_form_source('Edit Subject')
        edit_form.requires = 'case'
        edit_form.actions.case_preload = PreloadAction(preload={
            '/data/name': 'name',
            '/data/subject_study_id': 'subject_study_id',
            '/data/dob': 'dob',
            '/data/sex': 'sex',
            '/data/enrollment_date': 'enrollment_date',
        })
        edit_form.actions.case_preload.condition.type = 'always'
        edit_form.actions.update_case = UpdateCaseAction(update={
            'name': '/data/name',
            'subject_study_id': '/data/subject_study_id',
            'dob': '/data/dob',
            'sex': '/data/sex',
            'enrollment_date': '/data/enrollment_date',
        })
        edit_form.actions.update_case.condition.type = 'always'
        return module

    def get_new_app(self, domain_name, app_name, version=APP_V2):
        app = Application.new_app(domain_name, app_name, application_version=version)
        app.name = self.name
        subject_module = self.new_subject_module(app)
        for event in self.iter_events():
            module = event.new_module_for_app(app, subject_module)
            for study_form in event.iter_forms():
                study_form.add_new_form_to_module(module)
            # Add all the event's forms as a single form in the subject module
            # We do this to create the new event as a subcase of the subject
            event.add_form_to_subject_module(subject_module)
        return app


class StudyEvent(StudyObject):

    def __init__(self, defn, meta):
        super(StudyEvent, self).__init__(defn, meta)
        self.oid = defn.get('OID')
        self.name = defn.get('Name')
        self.is_repeating = defn.get('Repeating') == 'Yes'
        self.event_type = defn.get('Type')  # Scheduled, Unscheduled, or Common
        self.unique_id = self.oid.lower()

    def iter_forms(self):
        for form_ref in self.defn.xpath('./odm:FormRef', namespaces=odm_nsmap):
            form_oid = form_ref.get('FormOID')
            form_def = self.meta.xpath('./odm:FormDef[@OID="{}"]'.format(form_oid), namespaces=odm_nsmap)[0]
            yield StudyForm(form_def, self.meta)

    def new_module_for_app(self, app, subject_module):
        """
        Return a CommCare module
        """
        module = app.add_module(Module.new_module(self.name, None))
        module.unique_id = self.unique_id
        module.case_type = 'event'
        module.root_module_id = subject_module.unique_id
        module.parent_select.active = True
        module.parent_select.module_id = subject_module.unique_id
        return module

    def add_form_to_subject_module(self, subject_module):
        form_name = 'Schedule ' + self.name
        xform = XFormBuilder(form_name)
        xform.new_question('start_date', 'Start Date', data_type='date')
        xform.new_question('start_time', 'Start Time', data_type='time')
        xform.new_question('subject_name', None, data_type=None)  # Hidden value
        xform.new_question('name', None, data_type=None,
                           calculate="concat('{} ', /data/start_date, ' ', /data/start_time, "
                                     "' (', /data/subject_name, ')')".format(self.name))
        for study_form in self.iter_forms():
            study_form.add_item_groups_to_xform(xform)
        form = subject_module.new_form(form_name, None)
        form.unique_id = self.unique_id + '_form'
        form.source = xform.tostring(pretty_print=True, encoding='utf-8', xml_declaration=True)
        form.requires = 'case'
        form.actions.case_preload = PreloadAction(preload={
            '/data/subject_name': 'name'
        })
        form.actions.case_preload.condition.type = 'always'
        form.actions.subcases.append(OpenSubCaseAction(
            case_type='event',
            case_name='/data/name',
            case_properties={
                'start_date': '/data/start_date',
                'start_time': '/data/start_time',
            },
            condition=FormActionCondition(type='always')
        ))


class StudyForm(StudyObject):

    def __init__(self, defn, meta):
        super(StudyForm, self).__init__(defn, meta)
        self.oid = defn.get('OID')
        self.name = defn.get('Name')
        self.is_repeating = defn.get('Repeating') == 'Yes'

    def iter_item_groups(self):
        for ig_ref in self.defn.xpath('./odm:ItemGroupRef', namespaces=odm_nsmap):
            ig_oid = ig_ref.get('ItemGroupOID')
            ig_def = self.meta.xpath('./odm:ItemGroupDef[@OID="{}"]'.format(ig_oid), namespaces=odm_nsmap)[0]
            yield ItemGroup(ig_def, self.meta)

    def add_new_form_to_module(self, module):
        """
        Add a CommCare form based in this form's item groups and items to a given CommCare module
        """
        form = module.new_form(self.name, None)
        form.unique_id = make_uuid()
        form.source = self.build_xform()
        # Must require case for case list to work
        form.requires = 'case'
        form.actions.case_preload = PreloadAction(preload={
            '/data/start_date': 'start_date',
            '/data/start_time': 'start_time',
        })
        form.actions.case_preload.condition.type = 'always'

    def add_item_groups_to_xform(self, xform):
        for ig in self.iter_item_groups():
            data_type = 'repeatGroup' if self.is_repeating else 'group'
            group = xform.new_group(ig.question_name, ig.question_label, data_type)
            for item in ig.iter_items():
                group.new_question(item.question_name, item.question_label, ODK_DATA_TYPES[item.data_type],
                                   choices=item.choices)

    def build_xform(self):
        xform = XFormBuilder(self.name)
        xform.new_question('start_date', 'Start Date', data_type='date')
        xform.new_question('start_time', 'Start Time', data_type='time')
        self.add_item_groups_to_xform(xform)
        return xform.tostring(pretty_print=True, encoding='utf-8', xml_declaration=True)


class ItemGroup(StudyObject):

    def __init__(self, defn, meta):
        super(ItemGroup, self).__init__(defn, meta)
        self.oid = defn.get('OID')
        self.name = defn.get('Name')
        self.is_repeating = defn.get('Repeating') == 'Yes'
        self.sas_dataset_name = defn.get('SASDatasetName')
        self.comment = defn.get('Comment')

        self.question_name = self.oid.lower()
        self.question_label = self.name

    def iter_items(self):
        for item_ref in self.defn.xpath('./odm:ItemRef', namespaces=odm_nsmap):
            item_oid = item_ref.get('ItemOID')
            item_def = self.meta.xpath('./odm:ItemDef[@OID="{}"]'.format(item_oid), namespaces=odm_nsmap)[0]
            yield Item(item_def, self.meta, self)


class Item(StudyObject):

    def __init__(self, defn, meta, item_group):
        super(Item, self).__init__(defn, meta)
        self.oid = defn.get('OID')
        self.name = defn.get('Name')
        self.data_type = defn.get('DataType')
        self.length = defn.get('Length')
        self.sas_field_name = defn.get('SASFieldName')
        self.comment = defn.get('Comment')
        self.item_group = item_group

        cl_ref = defn.xpath('./odm:CodeListRef', namespaces=odm_nsmap)
        if cl_ref:
            self.data_type = 'select1'
            self.choices = self.get_choices(cl_ref[0].get('CodeListOID'))
        else:
            self.choices = None

        self.question_name = self.oid.lower()
        text = defn.xpath('./odm:Question/odm:TranslatedText', namespaces=odm_nsmap)
        self.question_label = text[0].text.strip() if text else self.name

    def get_choices(self, cl_oid):
        choices = {}
        cl_def = self.meta.xpath('./odm:CodeList[@OID="{}"]'.format(cl_oid), namespaces=odm_nsmap)[0]
        for cl_item in cl_def:
            value = cl_item.get('CodedValue')
            label = cl_item.xpath('./odm:Decode/odm:TranslatedText', namespaces=odm_nsmap)[0].text
            choices[value] = label
        return choices


class Command(BaseCommand):
    help = 'Create an application from an ODM document in the given domain'
    args = '<domain> <app-slug> <odm-doc>'

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
