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
from custom.openclinica.const import (
    CC_SUBJECT_KEY,
    CC_STUDY_SUBJECT_ID,
    CC_DOB,
    CC_SEX,
    CC_ENROLLMENT_DATE,
)
from custom.openclinica.utils import odm_nsmap, quote_nan


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
        # e.g.
        #     <StudyName>An open-label, non-randomized study on Captopril</StudyName>
        #     <StudyDescription>
        #         Researcher KEMRI/ CREATES Director
        #     </StudyDescription>
        #     <ProtocolName>BE 01/2014</ProtocolName>
        self.description = defn.xpath('./odm:GlobalVariables/odm:StudyDescription', namespaces=odm_nsmap)[0].text
        # identifier is "Unique Protocol ID" in UI, "ProtocolName" in ODM, and "identifier" in OpenClinica API
        self.identifier = defn.xpath('./odm:GlobalVariables/odm:ProtocolName', namespaces=odm_nsmap)[0].text

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
        xform.new_question(CC_SUBJECT_KEY, 'Person ID')  # Unique ID. aka "Screening Number", "Subject Key"
        xform.new_question(CC_STUDY_SUBJECT_ID, 'Subject Study ID')  # Subject number for this study
        xform.new_question(CC_DOB, 'Date of Birth', data_type='date')
        xform.new_question(CC_SEX, 'Sex', data_type='select1', choices={1: 'Male', 2: 'Female'})
        xform.new_question(CC_ENROLLMENT_DATE, 'Enrollment Date', data_type='date')
        return xform.tostring(pretty_print=True)

    def new_subject_module(self, app):

        def add_reg_form_to_module(module_):
            reg_form = module_.new_form('Register Subject', None)
            reg_form.get_unique_id()
            reg_form.source = self.get_subject_form_source('Register Subject')
            reg_form.actions.open_case = OpenCaseAction(
                name_path='/data/name',
                external_id=None,
                condition=FormActionCondition(type='always')
            )
            reg_form.actions.update_case = UpdateCaseAction(
                update={
                    'subject_study_id': '/data/subject_study_id',
                    'dob': '/data/dob',
                    'sex': '/data/sex',
                    'enrollment_date': '/data/enrollment_date',
                },
                condition=FormActionCondition(type='always')
            )

        def add_edit_form_to_module(module_):
            edit_form = module_.new_form('Edit Subject', None)
            edit_form.get_unique_id()
            edit_form.source = self.get_subject_form_source('Edit Subject')
            edit_form.requires = 'case'
            preload = {
                '/data/name': 'name',
                '/data/subject_study_id': 'subject_study_id',
                '/data/dob': 'dob',
                '/data/sex': 'sex',
                '/data/enrollment_date': 'enrollment_date',
            }
            edit_form.actions.case_preload = PreloadAction(
                preload=preload,
                condition=FormActionCondition(type='always')
            )
            edit_form.actions.update_case = UpdateCaseAction(
                update={v: k for k, v in preload.items()},
                condition=FormActionCondition(type='always')
            )

        module = app.add_module(Module.new_module('Study Subjects', None))
        module.unique_id = 'study_subjects'
        module.case_type = 'subject'
        add_reg_form_to_module(module)
        add_edit_form_to_module(module)
        return module

    def get_new_app(self, domain_name, app_name, version=APP_V2):
        app = Application.new_app(domain_name, app_name, application_version=version)
        app.comment = self.name  # Study names can be long. cf. https://clinicaltrials.gov/
        subject_module = self.new_subject_module(app)
        for event in self.iter_events():
            module = event.new_module_for_app(app, subject_module)
            for study_form in event.iter_forms():
                study_form.add_form_to_module(module)
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

        def get_form_source(form_name_):
            xform = XFormBuilder(form_name_)
            # We want to know the time according to the user, but event start and end timestamps are actually
            # determined from form submission times.
            xform.new_question('start_date', 'Start Date', data_type='date')
            xform.new_question('start_time', 'Start Time', data_type='time')
            xform.new_question('subject_name', None, data_type=None)  # data_type=None makes this a hidden value
            xform.new_question('event_type', None, data_type=None,
                               value="'{}'".format(self.unique_id))  # Quote string default values
            xform.new_question('event_repeats', None, data_type=None,
                               value="'{}'".format(self.is_repeating).lower())
            xform.new_question('name', None, data_type=None,
                               calculate="concat('{} ', /data/start_date, ' ', /data/start_time, "
                                         "' (', /data/subject_name, ')')".format(self.name))
            for study_form in self.iter_forms():
                study_form.add_item_groups_to_xform(xform)
            xform.new_question('end_date', 'End Date', data_type='date')
            xform.new_question('end_time', 'End Time', data_type='time')
            return xform.tostring(pretty_print=True, encoding='utf-8', xml_declaration=True)

        def get_preload_action():
            return PreloadAction(
                preload={'/data/subject_name': 'name'},
                condition=FormActionCondition(type='always')
            )

        def get_open_subcase_action():
            props = {
                'start_date': '/data/start_date',
                'start_time': '/data/start_time',
                'end_date': '/data/end_date',
                'end_time': '/data/end_time',
                'event_type': '/data/event_type',
                'event_repeats': '/data/event_repeats',
            }
            # Save all properties to the case. We will use them to pre-populate the event's update forms (see
            # StudyForm.add_form_to_module) ... but we won't use them for the export. We will use all the form
            # submissions instead, so we can get an audit trail of all value changes for the ODM.
            for study_form in self.iter_forms():
                for item_group in study_form.iter_item_groups():
                    for item in item_group.iter_items():
                        props[item.question_name] = '/data/{}/{}'.format(
                            item_group.question_name,
                            item.question_name
                        )
            return OpenSubCaseAction(
                case_type='event',
                case_name='/data/name',
                case_properties=props,
                condition=FormActionCondition(type='always')
            )

        form_name = 'Schedule ' + self.name
        form = subject_module.new_form(form_name, None)
        form.get_unique_id()
        form.source = get_form_source(form_name)
        form.requires = 'case'
        form.actions.case_preload = get_preload_action()
        form.actions.subcases.append(get_open_subcase_action())


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

    def add_form_to_module(self, module):
        """
        Add a CommCare form of this form's item groups and items to a given CommCare module
        """
        def get_preload_action():
            preload = {
                '/data/start_date': 'start_date',
                '/data/start_time': 'start_time',
                '/data/end_date': 'end_date',
                '/data/end_time': 'end_time',
            }
            for item_group in self.iter_item_groups():
                for item in item_group.iter_items():
                    preload['/data/{}/{}'.format(
                        item_group.question_name,
                        item.question_name
                    )] = item.question_name
            return PreloadAction(
                preload=preload,
                condition=FormActionCondition(type='always')
            )

        def get_update_case_action():
            update = {
                'start_date': '/data/start_date',
                'start_time': '/data/start_time',
                'end_date': '/data/end_date',
                'end_time': '/data/end_time',
            }
            for item_group in self.iter_item_groups():
                for item in item_group.iter_items():
                    update[item.question_name] = '/data/{}/{}'.format(
                        item_group.question_name,
                        item.question_name
                    )
            return UpdateCaseAction(
                update=update,
                condition=FormActionCondition(type='always')
            )

        form = module.new_form(self.name, None)
        form.get_unique_id()
        form.source = self.build_xform()
        # Must require case for case list to work
        form.requires = 'case'
        form.actions.case_preload = get_preload_action()
        form.actions.update_case = get_update_case_action()

    def add_item_groups_to_xform(self, xform):
        for ig in self.iter_item_groups():
            data_type = 'repeatGroup' if self.is_repeating else 'group'
            group = xform.new_group(ig.question_name, ig.question_label, data_type)
            for item in ig.iter_items():
                params = {}
                if item.validation:
                    params['constraint'] = item.validation
                if item.validation_msg:
                    params['jr:constraintMsg'] = item.validation_msg
                group.new_question(item.question_name, item.question_label, ODK_DATA_TYPES[item.data_type],
                                   choices=item.choices, **params)

    def build_xform(self):
        xform = XFormBuilder(self.name)
        xform.new_question('start_date', 'Start Date', data_type='date')
        xform.new_question('start_time', 'Start Time', data_type='time')
        self.add_item_groups_to_xform(xform)
        xform.new_question('end_date', 'End Date', data_type='date')
        xform.new_question('end_time', 'End Time', data_type='time')
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

        # OpenClinica only includes RangeCheck in metadata. Regular expressions are supported in CRFs, but not in
        # CDISC ODM. cf. http://www.cdisc.org/system/files/all/generic/text/html/odm1_1_0.html#ItemDef
        # 3rd-party support: http://www.opencdisc.org/projects/validator/opencdisc-validation-framework#regex-rule
        range_checks = defn.xpath('./odm:RangeCheck', namespaces=odm_nsmap)
        if range_checks:
            self.validation, self.validation_msg = self.get_range_check_validation(range_checks)
        else:
            self.validation, self.validation_msg = None, None

    def get_choices(self, cl_oid):
        choices = {}
        cl_def = self.meta.xpath('./odm:CodeList[@OID="{}"]'.format(cl_oid), namespaces=odm_nsmap)[0]
        for cl_item in cl_def:
            value = cl_item.get('CodedValue')
            label = cl_item.xpath('./odm:Decode/odm:TranslatedText', namespaces=odm_nsmap)[0].text
            choices[value] = label
        return choices

    @staticmethod
    def get_condition(comparator, values):
        """
        Returns a CommCare validation condition given a CDISC ODM comparator and a list of values

        >>> Item.get_condition('LT', ['5'])
        '. < 5'

        """

        def value_in(values_):
            return '(' + ' or '.join(('. = ' + v for v in values_)) + ')'

        scalar_comparators = {
            'LT': '. < ',
            'LE': '. <= ',
            'GT': '. > ',
            'GE': '. >= ',
            'EQ': '. = ',
            'NE': '. != ',
        }
        vector_comparators = {
            'IN': lambda vv: value_in(vv),
            'NOTIN': lambda vv: 'not ' + value_in(vv)
        }

        if not values:
            raise ValueError('A validation condition needs at least one comparable value')
        quoted_values = [quote_nan(v) for v in values]
        if comparator in scalar_comparators:
            return scalar_comparators[comparator] + quoted_values[0]
        elif comparator in vector_comparators:
            return vector_comparators[comparator](quoted_values)
        else:
            raise ValueError('Unknown comparison operator "{}"'.format(comparator))

    def get_range_check_validation(self, range_checks):
        error_msg = ''
        conditions = []
        for check in range_checks:
            if check.get('SoftHard') and check.get('SoftHard').lower() != 'hard':
                # A soft constraint doesn't reject a value, it just produces a warning. We only support hard
                # constraints
                continue
            comparator = check.get('Comparator')
            values = [val.text for val in check.xpath('./odm:CheckValue', namespaces=odm_nsmap)]
            conditions.append(self.get_condition(comparator, values))
            text = check.xpath('./odm:ErrorMessage/odm:TranslatedText', namespaces=odm_nsmap)
            if text and not error_msg:
                error_msg = text[0].text.strip()
        return ' and '.join(conditions), error_msg


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
