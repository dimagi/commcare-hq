from __future__ import absolute_import

from subprocess import Popen, PIPE
import logging

#TODO: $PATH is sometimes notably different in a deployment environment, and 
#causes hard-to-catch bugs. this function should probably standardize the path,
#but how to do so cross-platform?
def shell_exec(cmd, cwd=None):
    """helper function to execute a command. returns stdout a la readlines().
    traps all exceptions. any stderr is logged, but not returned"""
    def process_output(raw):
        output = raw.split('\n')
        if not output[-1]:
            del output[-1]
        return output

    #note: be mindful of what's on the PATH!
    try:
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True, cwd=cwd)
        (out, err) = [process_output(data) for data in p.communicate()]
        if err:
            logging.warn('command [%s] returned error output [%s]' % (cmd, str(err)))
        return out
    except:
        #not sure exception can be thrown when executing via shell; playing it safe...
        logging.exception('exception executing [%s]' % cmd)
        return None


