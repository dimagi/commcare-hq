import logging
import logging.handlers
from subprocess import Popen, PIPE
import random



def initialize_logging(loginitfunc):
    if not hasattr(logging, '_initialized'):
        loginitfunc()
        logging.info('logging initialized')
        logging._initialized = True

def default_logging(logfile):
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    handlers = [
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(logfile, maxBytes=2**24, backupCount=3),
    ]

    for handler in handlers:
        handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(message)s'))
        root.addHandler(handler)

def shell_exec(cmd, cwd=None):
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

def get_revision(vcs, reporoot, dirtymode=None):
    REV_HASH_LENGTH = 12
    DIRTY_NONCE_LENGTH = 5

    #untracked files don't count as dirty
    if vcs == 'git':
        def raw_revision():
            return shell_exec('git log --format=%H -1', reporoot)
        def is_dirty(excl_untracked=True):
            return bool(shell_exec('git status --porcelain %s' % ('-uno' if excl_untracked else ''), reporoot))
    elif vcs == 'hg':
        def raw_revision():
            return shell_exec('hg parents --template "{node}"', reporoot)
        def is_dirty(excl_untracked=True):
            return bool(shell_exec('hg status %s' % ('-q' if excl_untracked else ''), reporoot))

    rev = raw_revision()
    if rev:
        rev = rev[0].strip()[:REV_HASH_LENGTH].lower()
    if not rev:
        return None

    dirty_suffix = ''
    if is_dirty():
        if dirtymode == 'flag':
            dirty_suffix = '*'
        elif dirtymode == 'nonce':
            dirty_suffix = '-%0*x' % (DIRTY_NONCE_LENGTH, random.getrandbits(DIRTY_NONCE_LENGTH * 4))

    return rev + dirty_suffix
