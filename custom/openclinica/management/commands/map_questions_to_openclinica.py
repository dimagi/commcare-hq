from collections import defaultdict
from lxml import etree
import os
from django.conf import settings
from django.core.management import BaseCommand
import sys
from corehq.apps.app_manager.util import all_apps_by_domain
from custom.openclinica.utils import simplify, Item, get_matching_start, odm_nsmap
import yaml


class Command(BaseCommand):

    # A dictionary of question: (study_event_oid, form_oid, item_group_oid, item_oid)
    question_item_map = {}

    def handle(self, *args, **options):
        odm_filename = os.path.join(settings.BASE_DIR, 'custom', 'openclinica', 'study_metadata.xml')
        odm_root = etree.parse(odm_filename)
        self.read_question_item_map(odm_root)
        data = self.read_forms()

        yaml_filename = os.path.join(settings.BASE_DIR, 'custom', 'openclinica', 'commcare_questions.yaml')
        with file(yaml_filename, 'w') as yaml_file:
            print >> yaml_file, '# CommCare questions mapped to OpenClinica form items'
            print >> yaml_file, '# To create, save study metadata from OpenClinica to '
            print >> yaml_file, '# custom/openclinica/study_metadata.xml and run '
            print >> yaml_file, '# `./manage.py map_questions_to_openclinica`.'
            yaml.dump(simplify(data), yaml_file, explicit_start=True, default_flow_style=False)

    @staticmethod
    def get_item_prefix(form_oid, ig_oid):
        """
        OpenClinica item OIDs are prefixed with "I_<prefix>_" where <prefix> is derived from the item's form OID

        (Dropping "I_<prefix>_" will give us the CommCare question name in upper case)
        """
        form_name = form_oid[2:]  # Drop "F_"
        ig_name = ig_oid[3:]  # Drop "IG_"
        prefix = get_matching_start(form_name, ig_name)
        if prefix.endswith('_'):
            prefix = prefix[:-1]
        return prefix

    def read_question_item_map(self, odm):
        # study_oid = odm.xpath('./odm:Study', namespaces=nsmap)[0].get('OID')
        meta_e = odm.xpath('./odm:Study/odm:MetaDataVersion', namespaces=odm_nsmap)[0]

        for se_ref in meta_e.xpath('./odm:Protocol/odm:StudyEventRef', namespaces=odm_nsmap):
            se_oid = se_ref.get('StudyEventOID')
            for form_ref in meta_e.xpath('./odm:StudyEventDef[@OID="{}"]/odm:FormRef'.format(se_oid),
                                         namespaces=odm_nsmap):
                form_oid = form_ref.get('FormOID')
                for ig_ref in meta_e.xpath('./odm:FormDef[@OID="{}"]/odm:ItemGroupRef'.format(form_oid),
                                           namespaces=odm_nsmap):
                    ig_oid = ig_ref.get('ItemGroupOID')
                    prefix = self.get_item_prefix(form_oid, ig_oid)
                    prefix_len = len(prefix) + 3  # len of "I_<prefix>_"
                    for item_ref in meta_e.xpath('./odm:ItemGroupDef[@OID="{}"]/odm:ItemRef'.format(ig_oid),
                                                 namespaces=odm_nsmap):
                        item_oid = item_ref.get('ItemOID')
                        question = item_oid[prefix_len:].lower()
                        self.question_item_map[question] = Item(se_oid, form_oid, ig_oid, item_oid)

    def read_forms(self):
        data = defaultdict(dict)
        for domain, pymodule in settings.DOMAIN_MODULE_MAP.iteritems():
            if pymodule == 'custom.openclinica':
                for app in all_apps_by_domain(domain):
                    for ccmodule in app.get_modules():
                        for ccform in ccmodule.get_forms():
                            form = data[ccform.xmlns]
                            form['app'] = app.name
                            form['module'] = ccmodule.name['en']
                            form['name'] = ccform.name['en']
                            form['questions'] = {}
                            for question in ccform.get_questions(['en']):
                                name = question['value'].split('/')[-1]
                                form['questions'][name] = self.question_item_map.get(name)
        return data
