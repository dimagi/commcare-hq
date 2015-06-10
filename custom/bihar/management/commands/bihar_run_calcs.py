import gevent
from corehq.apps.hqcase.dbaccessors import get_case_ids_in_domain_by_owner
from custom.bihar.models import CareBiharFluffPillow
from dimagi.utils.couch.database import iter_docs
from django.core.management import BaseCommand
from custom.bihar.utils import get_all_owner_ids_from_group
from casexml.apps.case.models import CommCareCase
from corehq.apps.groups.models import Group


class Command(BaseCommand):

    def handle(self, *args, **options):
        domain, group_name = args
        group = Group.by_name(domain, name=group_name)
        owner_ids = get_all_owner_ids_from_group(group)
        pillow = CareBiharFluffPillow()
        db = CommCareCase.get_db()

        greenlets = []

        def process_case(case):
            pillow.change_transport(pillow.change_transform(case))

        for i, owner_id in enumerate(owner_ids):
            print '{0}/{1} owner_ids'.format(i, len(owner_ids))
            case_ids = get_case_ids_in_domain_by_owner(
                domain, owner_id=owner_id)
            print '{0} case_ids'.format(len(case_ids))
            for case in iter_docs(db, case_ids):
                g = gevent.Greenlet.spawn(process_case, case)
                greenlets.append(g)
        gevent.joinall(greenlets)
