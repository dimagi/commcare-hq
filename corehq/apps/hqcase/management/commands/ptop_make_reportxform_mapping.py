import sys
import os

from django.core.management.base import NoArgsCommand
from django.conf import settings

from casexml.apps.case.models import CommCareCase
from corehq.apps.hqcase.management.commands.ptop_generate_mapping import MappingOutputCommand
from corehq.pillows.mappings import reportxform_mapping
from corehq.pillows.reportxform import ReportXFormPillow


class Command(MappingOutputCommand):
    help="Generate mapping JSON of our ES indexed types. For casexml"
    option_list = NoArgsCommand.option_list + (
    )
    doc_class_str = "casexml.apps.case.models.CommCareCase"
    doc_class = CommCareCase


    def finish_handle(self):
        filepath = os.path.join(settings.FILEPATH, 'corehq','pillows','mappings','reportxform_mapping.py')
        xform_pillow = ReportXFormPillow(create_index=False)

        #current index
        #check current index
        aliased_indices = xform_pillow.check_alias()

        current_index = xform_pillow.es_index

        sys.stderr.write("current index:\n")
        sys.stderr.write('REPORT_XFORM_INDEX="%s"\n' % current_index)

        #regenerate the mapping dict
        mapping = reportxform_mapping.REPORT_XFORM_MAPPING
        xform_pillow.default_mapping = mapping
        delattr(xform_pillow, '_calc_meta_cache')
        calc_index = "%s_%s" % (xform_pillow.es_index_prefix, xform_pillow.calc_meta())

        if calc_index not in aliased_indices and calc_index != current_index:
            sys.stderr.write("\n\tWarning, current index %s is not aliased at the moment\n" % current_index)
            sys.stderr.write("\tCurrent live aliased index: %s\n\n"  % (','.join(aliased_indices)))

        if calc_index != current_index:
            sys.stderr.write("REPORT_XFORM_INDEX hash has changed, please update \n\t%s\n\tREPORT_XFORM_INDEX property with the line below:\n" % filepath)
            sys.stdout.write('REPORT_XFORM_INDEX="%s"\n' % calc_index)
        else:
            sys.stderr.write("REPORT_XFORM_INDEX unchanged\n")




