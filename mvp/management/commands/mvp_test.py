from django.core.management.base import LabelCommand
from corehq.apps.indicators.models import FormIndicatorDefinition
from couchforms.models import XFormInstance
from mvp.models import MVP

class Command(LabelCommand):
    help = "."
    args = "<indicator type> <case type or xmlns>"
    label = ""

    def handle(self, *args, **options):
        self.apply_form_indicator_to_id("e8268b73-a42d-4fd9-89dd-4fc79e4271a7",
            MVP.VISIT_FORMS['child_visit'],
            "rdt_result"
        )

    def apply_form_indicator_to_id(self, form_id, xmlns, indicator_slug):
        print "Form ID", form_id
        print "XMLNS", xmlns
        print "Slug", indicator_slug
        form_indicator = FormIndicatorDefinition.get_current(
            MVP.NAMESPACE,
            MVP.DOMAINS[0],
            indicator_slug,
            xmlns=xmlns)
        print "Grabbed Indicator", form_indicator
        xform = XFormInstance.get(form_id)
        print "Grabbed XForm", xform
        xform.set_definition(form_indicator)
        xform.save()
        print "Set definition"