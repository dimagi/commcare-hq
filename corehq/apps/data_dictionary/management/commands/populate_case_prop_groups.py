from django.core.management.base import BaseCommand
from corehq.apps.data_dictionary.models import CaseProperty, CasePropertyGroup

from corehq.apps.domain.models import Domain
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    help = "Populates groups from caseproperty model to casepropertygroups model"

    def add_arguments(self, parser):
        parser.add_argument('domains', nargs='*',
            help="Domain name(s). If blank, will generate for all domains")

    def handle(self, **options):
        domains = options['domains'] or [d['key'] for d in Domain.get_all(include_docs=False)]
        print("Populating groups for {} domains".format(len(domains)))

        for domain in with_progress_bar(domains):
            populate_case_prop_groups(domain)


def populate_case_prop_groups(domain):
    filter_kwargs = {"case_type__domain": domain, "group_id__isnull": True}
    case_props = CaseProperty.objects.exclude(group__exact="").filter(**filter_kwargs)

    for case_prop in case_props:
        group = CasePropertyGroup.get_or_create(case_prop.group, domain, case_prop.case_type)
        case_prop.group_id = group
        case_prop.save()
