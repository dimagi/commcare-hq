import sh
from sh_verbose import ShVerbose


def get_git(path=None):
    return sh.git.bake('--no-pager', _cwd=path)


class OriginalBranch(object):
    def __init__(self, git=None):
        self.git = git or get_git()
        self.original_branch = None

    def __enter__(self):
        self.original_branch = git_current_branch(self.git)
        return self.original_branch

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.git.checkout(self.original_branch)


def git_current_branch(git=None):
    git = git or get_git()
    branch = sh.grep(git.branch('--no-color'), '^* ').strip()[2:]
    if branch.startswith('('):
        branch = git.log(
            '--no-color', '--pretty=oneline', n=1
        ).strip().split(' ')[0]
    return branch


def git_check_merge(branch1, branch2, git=None):
    """
    returns True if branch1 would auto-merge cleanly into branch2,
    False if the merge requires human assistance

    Thanks to http://stackoverflow.com/a/501461/240553

    """
    git = git or get_git()
    with ShVerbose(False):
        orig_branch = git_current_branch(git)
        git.checkout(branch2)
        is_behind = git.log('{0}..{1}'.format(branch2, branch1),
                            max_count=1).strip()
        if is_behind:
            try:
                git.merge('--no-commit', '--no-ff', branch1).strip()
            except sh.ErrorReturnCode_1:
                # git merge returns 1 when there's a conflict
                return False
            else:
                return True
            finally:
                git.merge('--abort')
                git.checkout(orig_branch)
        else:
            return True


def git_bisect_merge_conflict(branch1, branch2, git=None):
    """
    return the branch2 commit that prevents branch1 from being merged in

    """
    git = git or get_git()
    with OriginalBranch(git):
        try:
            base = git('merge-base', branch1, branch2).strip()
            if git_check_merge(branch1, branch2, git):
                return None
            assert git_check_merge(branch1, base, git)
            git.bisect('reset')
            txt = git.bisect('start', branch2, base, '--')
            while 'is the first bad commit' not in txt:
                commit = git_current_branch(git)
                if git_check_merge(branch1, commit, git):
                    txt = git.bisect('good')
                else:
                    txt = git.bisect('bad')
            return sh.grep(txt, '^commit ').strip().split(' ')[-1]
        finally:
            git.bisect('reset')


def _left_pad(padding, text):
    return padding + ('\n' + padding).join(text.split('\n'))


def print_one_way_merge_details(branch1, branch2, git):
    commit = git_bisect_merge_conflict(branch1, branch2, git)
    if commit:
        print '  * First conflicting commit on {0}:\n'.format(branch2)
        print _left_pad(' ' * 4, git.log('-n1', commit))
    else:
        print '  * No conflicting commits on {0}'.format(branch2)


def print_merge_details(branch1, branch2, git):
    print_one_way_merge_details(branch1, branch2, git)
    print_one_way_merge_details(branch2, branch1, git)


if __name__ == '__main__':
    import sys
    args = sys.argv[1:]
    options = ['show-conflict']
    try:
        option = args.pop(0)
    except IndexError:
        option = None
    if option == 'show-conflict':
        if len(args) == 2:
            print_merge_details(*args, git=get_git())
        else:
            print ('usage: python scripts/gitutils.py '
                   'show-conflict <branch1> <branch2>')
    else:
        print 'usage: python scripts/gitutils.py <command> [args...]\n'
        print 'Available commands:'
        print _left_pad('   ', '\n'.join(options))
