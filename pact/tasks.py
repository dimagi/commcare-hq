import logging
import traceback
from celery.task import task, subtask
from datetime import datetime
import simplejson
from couchforms.models import XFormInstance
from pact.enums import PACT_DOTS_DATA_PROPERTY
from pact.utils import get_case_id

@task(ignore_results=True)
def recompute_dots_caseblock(case_id):
    print "\trecompute_dots_caseblock %s" % case_id
    # next get pact_id information first off
#    pact_id = xform['form']['pact_id']
#    pts= PactPatient.view('pactcarehq/patient_pact_ids', key=pact_id, include_docs=True).all()
#    for pt in pts:
#        pt._cache_case(invalidate=True)
#        caseapi.recompute_dots_casedata(pt)
    pass


@task(ignore_results=True)
def eval_dots_block(xform_json, callback=None):
    """
    Evaluate the dots block in the xform submission and put it in the computed_ block for the xform.
    """
    print "eval_dots_block: %s" % xform_json['_id']
    case_id = get_case_id(xform_json)
    do_continue = False

    #first, set the pact_data to json if the dots update stuff is there.
    try:
        if xform_json.get(PACT_DOTS_DATA_PROPERTY, {}).has_key('processed'):
            print "\talready processed, skipping"
            return

        xform_json[PACT_DOTS_DATA_PROPERTY] = {}
        if not isinstance(xform_json['form']['case'].get('update', None), dict):
            pass
        else:
            #update is a dict
            if xform_json['form']['case']['update'].has_key('dots'):
                dots_json = xform_json['form']['case']['update']['dots']
                if isinstance(dots_json, str) or isinstance(dots_json, unicode):
                    json_data = simplejson.loads(dots_json)
                    xform_json[PACT_DOTS_DATA_PROPERTY]['dots'] = json_data
                    print "\tsaved doc: %s" % xform_json['_id']
                do_continue=True
            else:
                print "\tsaved doc, no dots data: %s" % xform_json['_id']
        xform_json[PACT_DOTS_DATA_PROPERTY]['processed']=datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        XFormInstance.get_db().save_doc(xform_json)

    except Exception, ex:
        #if this gets triggered, that's ok because web entry don't got them
        print "Doc %s error:%s" % (xform_json['_id'], ex)
#        tb = traceback.format_exc()
#        print tb
        logging.debug("Error, dots submission did not have a dots block in the update section: %s" % (ex))


    if callback is not None and do_continue:
        subtask(callback).delay(case_id)
