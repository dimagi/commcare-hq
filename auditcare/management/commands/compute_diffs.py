from optparse import make_option
from django.core.management.base import LabelCommand, NoArgsCommand
from couchdbkit.consumer import Consumer
import logging
import time
from auditcare import utils
from auditcare.models.couchmodels import AccessAudit, ModelActionAudit
from dimagi.utils.couch.database import get_db

class Command(NoArgsCommand):
    help = "Compute diff properties on all model changes."
    option_list = NoArgsCommand.option_list + (
        make_option('--recompute', action='store_true', dest='recompute',
            help='Recompute values.'),
    )
    def handle_noargs(self, **options):
        recompute = options.get('recompute', False)
        print recompute
        db = AccessAudit.get_db()
        vals = db.view('auditcare/model_actions_by_id', group=True, group_level=1).all()
        #get all model types
        model_dict= {x['key'][0]: x['value'] for x in vals}

        for model, count in model_dict.items():
            print "### %s" % (model)
            model_counts = db.view('auditcare/model_actions_by_id', group=True, startkey=[model,u''], endkey=[model,u'z']).all()

            #sort the models by id, then by rev descending
            #{u'value': <num>, u'key': [u'model', u'uuid']}
            for mc in model_counts:
                num = mc['value']
                model_uuid = mc['key'][1]
                #now for each model uuid, do a query again to get all the rev numbers
                item_revs = db.view('auditcare/model_actions_by_id', reduce=False, startkey=[model,model_uuid], endkey=[model,model_uuid]).all()
                revs = sorted([(x['id'], x['value']) for x in item_revs], key=lambda y: y[1], reverse=True)
                #tuples of (audit_id, rev_id)
                #print "%s:%s -> %s" % (model, model_uuid, revs)


                #ok, for each arr of revs, if it's length greater than 1, then do it
                if len(revs) > 1:
                    for i, t in enumerate(revs):
                        if i+1 == len(revs):
                            break
                        audit_id = t[0]
                        current = ModelActionAudit.get(audit_id)

                        next_audit_id = revs[i+1][0]
                        next = ModelActionAudit.get(next_audit_id)

                        #sanity check
                        if next.revision_checksum == current.revision_checksum:
                            continue

                        if (current.archived_data.get('doc_type', None) =='XFormInstance' and next.archived_data.get('doc_type', None) == 'XFormInstance'):
                            #it's an xforminstance
                            removed, added, changed = utils.dict_diff(current.archived_data['form'], next.archived_data['form'])
                        else:
                            removed, added, changed = utils.dict_diff(current.archived_data, next.archived_data)
                        current.removed = removed
                        current.added = added
                        current.changed = changed
                        current.save()









                    




