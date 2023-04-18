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
        remove_out_of_sync_prop_and_groups()
        domains = options['domains'] or [d['key'] for d in Domain.get_all(include_docs=False)]
        print("Populating groups for {} domains".format(len(domains)))

        for domain in with_progress_bar(domains):
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


def remove_out_of_sync_prop_and_groups():
    # Reset properties that a different value in group column than in group object name.
    properties_out_of_sync = (CaseProperty.objects
                            .filter(group_obj__isnull=False)
                            .filter(~Q(group_obj__name=F('group'))))
    changed_properties = [prop.name for prop in properties_out_of_sync]
    print("Reset out of sync groups for {} properties".format(len(properties_out_of_sync)))
    print(changed_properties)
    properties_out_of_sync.update(group_obj=None)

    # Remove groups which dont have any properties
    group_without_properties = CasePropertyGroup.objects.filter(property__isnull=True)
    removed_groups = [group.name for group in group_without_properties]
    print("Removing {} groups without properties".format(len(group_without_properties)))
    print(removed_groups)
    group_without_properties.delete()
