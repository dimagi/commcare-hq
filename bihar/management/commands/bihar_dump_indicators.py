from couchdbkit import ResourceNotFound
from django.core.management import BaseCommand
from bihar.utils import get_all_calculations, get_calculation, \
    get_all_owner_ids_from_group
from corehq.apps.groups.models import Group


class Command(BaseCommand):
    """Nice to pipe this into pbcopy (mac only?) and then paste into excel"""

    def handle(self, *args, **options):
        args = list(args)
        domain = args.pop(0)
        group_id_or_name = args.pop(0)
        slug = args.pop(0) if args else None

        try:
            group = Group.get(group_id_or_name)
            assert group.domain == domain
        except ResourceNotFound:
            group = Group.by_name(domain, group_id_or_name)

        owner_ids = get_all_owner_ids_from_group(group)

        if slug:
            lines = [get_calculation(owner_ids, slug)]
        else:
            lines = get_all_calculations(owner_ids)

        for line in lines:
            print '\t'.join(map(unicode, line))