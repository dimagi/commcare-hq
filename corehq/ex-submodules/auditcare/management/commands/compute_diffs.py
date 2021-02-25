from django.core.management.base import BaseCommand

from auditcare.models import AccessAudit, ModelActionAudit


class Command(BaseCommand):
    help = "Recompute diff properties on all model changes, and set next/prev pointers"

    def add_arguments(self, parser):
        parser.add_argument(
            '--recompute',
            action='store_true',
            default=False,
            dest='recompute',
            help='Recompute values.',
        )

    def handle(self, **options):
        recompute = options['recompute']
        print(recompute)
        db = AccessAudit.get_db()
        vals = db.view('auditcare/model_actions_by_id', group=True, group_level=1).all()
        model_dict = {x['key'][0]: x['value'] for x in vals}

        for model, count in model_dict.items():
            #for each model type, query ALL audit instances.
            print("### %s" % (model))
            model_counts = db.view(
                'auditcare/model_actions_by_id', group=True, startkey=[model, ''], endkey=[model, 'z']
            ).all()
            #within a given model, query ALL instances

            #sort the models by id, then by rev descending
            #{u'value': <num>, u'key': [u'model', u'uuid']}
            for mc in model_counts:
                model_uuid = mc['key'][1]
                #now for each model uuid, do a query again to get all the rev numbers
                item_revs = db.view(
                    'auditcare/model_actions_by_id',
                    reduce=False,
                    startkey=[model, model_uuid],
                    endkey=[model, model_uuid]
                ).all()
                revs = sorted([(x['id'], x['value']) for x in item_revs], key=lambda y: y[1], reverse=True)
                #tuples of (audit_id, rev_id)
                #print "%s:%s -> %s" % (model, model_uuid, revs)

                #ok, for each arr of revs, if it's length greater than 1, then do it
                #we're going backwards, so...yeah
                if len(revs) > 1:
                    for i, t in enumerate(revs):
                        audit_id = t[0]
                        current = ModelActionAudit.get(audit_id)

                        if i + 1 == len(revs):
                            current.prev_id = None
                            current.save()
                            break

                        prev_audit_id = revs[i + 1][0]
                        prev_rev = ModelActionAudit.get(prev_audit_id)

                        if i == 0:
                            current.next_id = None

                        if current.prev_id != prev_rev._id:
                            current.prev_id = prev_rev._id
                            #current saves later
                        if prev_rev.next_id != current._id:
                            prev_rev.next_id = current._id
                            prev_rev.save()

                        current.compute_changes(save=True)
