from couchforms.signals import xform_saved
import logging

def process_cases(sender, xform, **kwargs):
    """Creates or updates case objects which live outside of the form"""
    # recursive import fail
    from corehq.apps.case.xform import get_or_update_cases
    try:
        cases = get_or_update_cases(xform)
        map(lambda pair: pair[1].save(), cases.items())
    except Exception, e:
        logging.exception(e)
        raise
    
# demo for showing how this can be done
# set to True or just remove check to do this always
AUTO_PROCESS_CASES = True   

if AUTO_PROCESS_CASES:
    xform_saved.connect(process_cases)