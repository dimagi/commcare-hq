from datetime import datetime
import hashlib
import pprint
from django.core.management.base import NoArgsCommand
import sys
import os
from casexml.apps.case.models import CommCareCase
from corehq.apps.hqcase.management.commands.ptop_generate_mapping import MappingOutputCommand
from corehq.pillows import dynamic
from corehq.pillows.dynamic import DEFAULT_MAPPING_WRAPPER, case_special_types, case_nested_types
from django.conf import settings
from corehq.pillows.mappings import reportcase_mapping
from corehq.pillows.reportcase import ReportCasePillow


class Command(MappingOutputCommand):
    help="Generate mapping JSON of our ES indexed types. For casexml"
    option_list = NoArgsCommand.option_list + (
    )
    doc_class_str = "casexml.apps.case.models.CommCareCase"
    doc_class = CommCareCase


    def finish_handle(self):

        filepath = os.path.join(settings.FILEPATH, 'corehq','pillows','mappings','reportcase_mapping.py')
        casepillow = ReportCasePillow(create_index=False)

        #current index
        #check current index
        aliased_indices = casepillow.check_alias()

        current_index = casepillow.es_index

        sys.stderr.write("current index:\n")
        sys.stderr.write('REPORT_CASE_INDEX="%s"\n' % current_index)

        #regenerate the mapping dict
        mapping = reportcase_mapping.REPORT_CASE_MAPPING
        casepillow.default_mapping = mapping
        delattr(casepillow, '_calc_meta_cache')
        calc_index = "%s_%s" % (casepillow.es_index_prefix, casepillow.calc_meta())

        if calc_index not in aliased_indices and calc_index != current_index:
            sys.stderr.write("\n\tWarning, current index %s is not aliased at the moment\n" % current_index)
            sys.stderr.write("\tCurrent live aliased index: %s\n\n"  % (','.join(aliased_indices)))

        if calc_index != current_index:
            sys.stderr.write("REPORT_CASE_INDEX hash has changed, please update \n\t%s\n\tREPORT_CASE_INDEX property with the line below:\n" % filepath)
            sys.stdout.write('REPORT_CASE_INDEX="%s"\n' % calc_index)
        else:
            sys.stderr.write("REPORT_CASE_INDEX unchanged\n")





