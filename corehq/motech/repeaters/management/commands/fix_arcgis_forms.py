from django.core.management.base import BaseCommand

from lxml import etree
from lxml.builder import E

from corehq.apps.reports.formdetails.readable import (
    get_data_cleaning_data,
    get_readable_data_for_submission,
)
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import XFormInstance
from corehq.motech.repeaters.models import Repeater


class Command(BaseCommand):
    help = """
    Fixes form question values for forwarding to ArcGIS.
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('-i', '--form-id')
        parser.add_argument('-f', '--form-id-file')
        parser.add_argument('-r', '--repeater-id')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, domain, *args, **options):
        if not options['form_id'] and not options['form_id_file']:
            self.stderr.write(
                'Please provide a form ID or a file containing form IDs.'
            )
            return
        if options['form_id'] and options['form_id_file']:
            self.stderr.write(
                'Please provide either a form ID or a file containing form '
                'IDs, not both.'
            )
            return

        if options['repeater_id']:
            repeater = Repeater.objects.get(id=options['repeater_id'])
        else:
            repeater = None

        interface = FormProcessorInterface(domain)
        if options['form_id']:
            form = fix_form(domain, options['form_id'], interface, options['dry_run'])
            if form and repeater:
                repeater.register(form)
        else:
            with open(options['form_id_file'], 'r') as form_id_file:
                form_ids = (line.strip() for line in form_id_file.readlines())
                for form_id in form_ids:
                    form = fix_form(domain, form_id, interface, options['dry_run'])
                    if form and repeater:
                        repeater.register(form)


def fix_form(domain, form_id, interface, dry_run=False):
    """
    Based on the "Clean Form Submission" code at
    `corehq/apps/reports/views.py::edit_form()`, but adds a new
    question group for ArcGIS indicators, which "Clean Form Submission"
    doesn't support.
    """
    instance = XFormInstance.objects.get_form(form_id, domain)
    xml = instance.get_xml_element()
    if xml.find('./indicateurs_arcgis', xml.nsmap) is not None:
        return None  # This form is already correct

    # `form_data` looks like, for example:
    # [FormQuestionResponse(
    #   calculate=None,
    #   children=[],
    #   comment=None,
    #   data_source={},
    #   group=None,
    #   label='Name',
    #   options=[],
    #   relevant=None,
    #   repeat=None,
    #   required=False,
    #   response='Zero',
    #   setvalue=None,
    #   tag='input',
    #   translations={},
    #   type='Text',
    #   value='/data/name',
    #   constraint=None,
    #   hashtagValue='#form/name',
    #   is_group=False,
    #   label_ref='name-label',
    # )]
    form_data, __ = get_readable_data_for_submission(instance)

    # `question_response_map` looks like, for example:
    # {'/data/name': {
    #     'label': 'Name',
    #     'icon': 'fcc fcc-fd-text',
    #     'value': 'Zero',
    #     'options': [],
    #     'splitName': '/\u200bdata/\u200bname',
    # }}
    question_response_map, __ = get_data_cleaning_data(form_data, instance)

    def q(question):
        # Utility function to get `question_response_map[question]`
        return get_value(question_response_map.get(question, ''))

    def get_value(val):
        # The values in `question_response_map` are _sometimes_ dicts
        # See corehq/apps/reports/views.py:1703
        return val.get('value', '') if isinstance(val, dict) else val

    # Build the "ArcGIS Indicators" question group based on
    # https://docs.google.com/spreadsheets/d/11MhkYXJd6ZxLYDX-5sC1UpxpvehQf4Cwz5nzgUY8VbY/edit?gid=0#gid=0
    arcgis_elem = (
        E.indicateurs_arcgis(
            E.arcgis_member_code(
                # if(#form/membre_infos/membre_oncho_campagne_case_exist = 'oui', 0, 1)
                '0' if q('/data/membre_infos/membre_oncho_campagne_case_exist') == 'oui' else '1'
            ),
            E.arcgis_nbre_personnes_traitees(
                # cond(#form/administrer_dose/accept_ivermectine = 'oui', 1, 0)
                '1' if q('/data/administrer_dose/accept_ivermectine') == 'oui' else '0'
            ),
            E.arcgis_refus(
                # cond(#form/administrer_dose/accept_ivermectine = 'non', 1, 0)
                '1' if q('/data/administrer_dose/accept_ivermectine') == 'non' else '0'
            ),
            E.arcgis_refus_jugule(
                # cond(#form/administrer_dose/accept_ivermectine = 'oui'
                #      and #form/load_campagne_oncho/accept_ivermectine = 'non',
                #      1,
                #      0
                # )
                '1' if (
                    q('/data/administrer_dose/accept_ivermectine') == 'oui'
                    and q('/data/load_campagne_oncho/accept_ivermectine') == 'non'
                ) else '0'
            ),
            E.arcgis_nbr_absent(
                # cond(#form/load_campagne_oncho/beneficiaire_present != 'non'
                #      and #form/presence/beneficiaire_present = 'non',
                #      1,
                #      #form/load_campagne_oncho/beneficiaire_present = 'non'
                #      and #form/presence/beneficiaire_present = 'oui',
                #      -1,
                #      0
                # )
                '1' if (
                    q('/data/load_campagne_oncho/beneficiaire_present') != 'non'
                    and q('/data/presence/beneficiaire_present') == 'non'
                ) else '-1' if (
                    q('/data/load_campagne_oncho/beneficiaire_present') == 'non'
                    and q('/data/presence/beneficiaire_present') == 'oui'
                ) else '0'
            ),
            E.arcgis_a_revisiter(
                # cond(#form/load_campagne_oncho/a_revisiter = 0
                #      and #form/membre_infos/a_revisiter = 1,
                #      1,
                #      #form/load_campagne_oncho/a_revisiter = 1
                #      and #form/membre_infos/a_revisiter = 0,
                #      -1,
                #      0
                # )
                '1' if (
                    q('/data/load_campagne_oncho/a_revisiter') == '0'
                    and q('/data/membre_infos/a_revisiter') == '1'
                ) else '-1' if (
                    q('/data/load_campagne_oncho/a_revisiter') == '1'
                    and q('/data/membre_infos/a_revisiter') == '0'
                ) else '0'
            ),
            E.arcgis_nbr_revisite(
                # if(#form/load_campagne_oncho/visit_count = 2, 1, 0)
                '1' if q('/data/load_campagne_oncho/visit_count') == '2' else '0'
            ),
            E.arcgis_dose_administree(
                # if(#form/administrer_dose/dose_administree != '',
                #    #form/administrer_dose/dose_administree,
                #    0
                # )
                q('/data/administrer_dose/dose_administree') if (
                    q('/data/administrer_dose/dose_administree') != ''
                ) else '0'
            ),
            E.arcgis_date_administration_dose(
                # #form/administrer_dose/date_administration_dose
                q('/data/administrer_dose/date_administration_dose')
            ),
            E.arcgis_heure_administration_dose(
                # #form/administrer_dose/heure_administration_dose
                q('/data/administrer_dose/heure_administration_dose')
            ),
        )
    )
    xml.append(arcgis_elem)

    if dry_run:
        print(etree.tostring(xml, pretty_print=True).decode('utf-8'))
        return None

    existing_form = XFormInstance.objects.get_with_attachments(form_id, domain)
    existing_form, new_form = interface.processor.new_form_from_old(
        existing_form,
        xml,
        None,  # `value_responses_map` param is unused
        instance.user_id,
    )
    interface.save_processed_models([new_form, existing_form])
    return new_form
