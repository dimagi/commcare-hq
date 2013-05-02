import sys
import os

from django.core.management.base import NoArgsCommand
from django.conf import settings

from casexml.apps.case.models import CommCareCase
from corehq.apps.hqcase.management.commands.ptop_generate_mapping import MappingOutputCommand
from corehq.pillows.fullxform import FullXFormPillow
from corehq.pillows.mappings import xform_mapping


class Command(MappingOutputCommand):
    help="Generate mapping JSON of our ES indexed types. For casexml"
    option_list = NoArgsCommand.option_list + (
    )
    doc_class_str = "casexml.apps.case.models.CommCareCase"
    doc_class = CommCareCase


    def finish_handle(self):
        filepath = os.path.join(settings.FILEPATH,'corehq','pillows','mappings','fullxform_mapping.py')
        full_xform_pillow = FullXFormPillow(create_index=False)

        #current index
        #check current index
        aliased_indices = full_xform_pillow.check_alias()

#        current_index = '%s_%s' % (xform_pillow.es_index_prefix, xform_pillow.calc_meta())
        current_index = full_xform_pillow.es_index

        sys.stderr.write("current index:\n")
        sys.stderr.write('XFORM_INDEX="%s"\n' % current_index)

        #regenerate the mapping dict
        mapping = xform_mapping.XFORM_MAPPING
        full_xform_pillow.default_mapping = mapping
        delattr(full_xform_pillow, '_calc_meta_cache')
        calc_index = "%s_%s" % (full_xform_pillow.es_index_prefix, full_xform_pillow.calc_meta())



        if calc_index not in aliased_indices and calc_index != current_index:
            sys.stderr.write("\n\tWarning, current index %s is not aliased at the moment\n" % current_index)
            sys.stderr.write("\tCurrent live aliased index: %s\n\n"  % (','.join(aliased_indices)))

        if calc_index != current_index:
            sys.stderr.write("FULL_XFORM_INDEX hash has changed, please update \n\t%s\n\tXFORM_INDEX property with the line below:\n" % filepath)
            sys.stdout.write('FULL_XFORM_INDEX="%s"\n' % calc_index)
        else:
            sys.stderr.write("FULL_XFORM_INDEX unchanged\n")




