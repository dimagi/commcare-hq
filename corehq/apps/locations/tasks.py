from celery.task import task, periodic_task
from celery.schedules import crontab, schedule
from django.core.cache import cache
from dimagi.utils.couch.database import get_db
from corehq.apps.locations.models import Location

@periodic_task(run_every=crontab(minute=0, hour=20))
def reparent_location_linked_docs():
    reparented_locs = [row['id'] for row in get_db().view('locations/post_move_processing')]
    for loc_id in reparented_locs:
        reparent_linked_docs(loc_id)

def reparent_linked_docs(loc_id):
    # NOTE this updates linked docs for this location and all its descendant locations, but we never
    # actually update the paths of the descendant locations themselves. we get around this right now
    # by disallowing re-parenting of non-leaf locs. and if we did allow it, we'd want to update the
    # paths of the descendant locations immediately instead of in a batch job

    db = get_db()
    loc = Location.get(loc_id)

    startkey = [loc.domain, loc._id]
    linked_docs = [row['doc'] for row in db.view('locations/linked_docs', startkey=startkey, endkey=startkey + [{}], include_docs=True)]

    for doc in linked_docs:
        cur_path = doc['location_']
        descendant_suffix = cur_path[cur_path.index(loc._id)+1:]
        doc['location_'] = loc.path + descendant_suffix
        db.save_doc(doc)
    # TODO is it faster to save all docs in bulk?

    # think there's a slight possibility that newly submitted docs could slip through the cracks
    # but probably only if this task runs very shortly after the location is moved. don't worry
    # about this for now... maybe have a more comprehensive clean-up job (expensive) that runs
    # less frequently

    delattr(loc, 'flag_post_move')
    loc.save()

