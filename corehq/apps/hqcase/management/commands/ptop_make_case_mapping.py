import sys
import os

from django.core.management.base import NoArgsCommand
from django.conf import settings

from corehq.apps.hqcase.management.commands.ptop_generate_mapping import MappingOutputCommand
from corehq.pillows.case import CasePillow
from corehq.pillows.mappings import case_mapping


class Command(MappingOutputCommand):
    help = "Recalculate hash of the casexml mapping (now hand made/maintained). run this anytime you modify case_mapping"
    option_list = NoArgsCommand.option_list + (
    )
    doc_class_str = "" #artifact of the mapping output command

    def finish_handle(self):
        filepath = os.path.join(settings.FILEPATH, 'corehq','pillows','mappings','case_mapping.py')
        case_pillow = CasePillow(create_index=False)

        #check current index
        current_index = case_pillow.es_index

        sys.stderr.write("current index:\n")
        sys.stderr.write('CASE_INDEX="%s"\n' % current_index)

        #regenerate the mapping dict
        mapping = case_mapping.CASE_MAPPING
        case_pillow.default_mapping = mapping
        delattr(case_pillow, '_calc_meta_cache')
        calc_index = "%s_%s" % (case_pillow.es_index_prefix, case_pillow.calc_meta())

        #aliased_indices = case_pillow.check_alias()
        # if calc_index not in aliased_indices and calc_index != current_index:
        #     sys.stderr.write("\n\tWarning, current index %s is not aliased at the moment\n" % current_index)
        #     sys.stderr.write("\tCurrent live aliased index: %s\n\n"  % (','.join(aliased_indices)))

        if calc_index != current_index:
            sys.stderr.write("############# HEADS UP!!! #################\n")
            sys.stderr.write("CASE_INDEX hash has changed, please update \n\t%s\n\tCASE_INDEX property with the line below:\n" % filepath)
            sys.stdout.write('CASE_INDEX="%s"\n' % calc_index)
        else:
            sys.stderr.write("CASE_INDEX unchanged\n")

