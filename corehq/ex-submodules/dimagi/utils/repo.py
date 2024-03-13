from .system import shell_exec


def get_revision(vcs, reporoot, dirtyfunc=lambda rev, **kw: rev + '*'):
    """return a revision string for the current state of the repository.
    returns None if installation does not appear to be a repository.
    vcs -- version control system in use: 'git' or 'hg'
    reporoot -- root directory of the repo (though usually any directory inside
      the repo will do
    dirtysuffix -- function that manipulates the revision if the repo is dirty
      args: (current revision, repo root)"""
    revinfo = get_raw_revision(vcs, reporoot)
    if not revinfo:
        return None

    rev, dirty = revinfo
    return dirtyfunc(rev, repo=reporoot, vcs=vcs) if dirty and dirtyfunc is not None else rev


def get_raw_revision(vcs, reporoot, untracked_is_dirty=False):
    """return the current revision of the repository and whether the working
    directory is clean. returns None if repo info cannot be fetched.
    untracked_is_dirty -- whether the presence of untracked files in the
      working directory is counted as 'not clean'"""
    REV_HASH_LENGTH = 12

    funcs = {
        'git': {
            'rev': git_raw_revision,
            'dirty': git_is_dirty,
        },
        'hg': {
            'rev': hg_raw_revision,
            'dirty': hg_is_dirty,
        }
    }
    
    def exec_(cmd):
        return shell_exec(cmd, reporoot)

    rev = funcs[vcs]['rev'](exec_)
    if rev:
        rev = rev[0].strip()[:REV_HASH_LENGTH].lower()
    if not rev:
        return None

    dirty = funcs[vcs]['dirty'](exec_, not untracked_is_dirty)
    return (rev, dirty)


def git_raw_revision(exec_):
    return exec_('git log --format=%H -1')


def hg_raw_revision(exec_):
    return exec_('hg parents --template "{node}"')


def git_is_dirty(exec_, excl_untracked):
    return bool(exec_('git status --porcelain %s' % ('-uno' if excl_untracked else '')))


def hg_is_dirty(exec_, excl_untracked):
    return bool(exec_('hg status %s' % ('-q' if excl_untracked else '')))


def dirty_nonce(rev, NONCE_LEN=5, **kwargs):
    """a dirtyfunc for get_revision"""
    import uuid
    return '%s-%s' % (rev, uuid.uuid4().hex[:NONCE_LEN])
