from django.core.management.base import BaseCommand
from django.db.models import Q, F
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
            remove_out_of_sync_prop_and_groups(domain)
            populate_case_prop_groups(domain)


def populate_case_prop_groups(domain):
    filter_kwargs = {"case_type__domain": domain, "group_obj__isnull": True}
    case_props = CaseProperty.objects.exclude(group__exact="").filter(**filter_kwargs)

    for case_prop in case_props:
        group, created = CasePropertyGroup.objects.get_or_create(
            name=case_prop.group,
            case_type=case_prop.case_type
        )
        case_prop.group_obj = group
        case_prop.save()


def remove_out_of_sync_prop_and_groups(domain):
    # Reset properties that a different value in group column than in group object name.
    properties_out_of_sync = (CaseProperty.objects
                            .filter(case_type__domain=domain, group_obj__isnull=False)
                            .filter(~Q(group_obj__name=F('group'))))
    print("Reset out of sync groups for {} properties".format(len(properties_out_of_sync)))
    for prop in properties_out_of_sync:
        print("Reset group for: {} in case_type: {}, domain: {}".format(
            prop.name, prop.case_type.name, domain
        ))
        prop.group_obj = None
        prop.save()

    # Remove groups which dont have any properties
    group_without_properties = CasePropertyGroup.objects.filter(case_type__domain=domain, property__isnull=True)
    print("Removing {} groups without properties".format(len(group_without_properties)))
    for group in group_without_properties:
        print("Removing group: {} in case_type: {}, domain: {}".format(
            group.name, group.case_type.name, domain
        ))
        group.delete()
