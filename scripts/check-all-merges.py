import sh
from gitutils import get_git, git_submodules, OriginalBranch
from rebuildstaging import BranchConfig, check_merges


def get_unmerged_remote_branches(git=None):
    git = git or get_git()
    try:
        lines = sh.grep(
            git.branch('--remote', '--no-merged', 'origin/master'),
            '^  origin',
        ).strip().split('\n')
    except sh.ErrorReturnCode_1:
        lines = []
    branches = [line.strip()[len('origin/'):] for line in lines]
    return branches


def make_full_config(path=None):
    def _make_full_config(path):
        path_prefix = '{}/'.format(path) if path else ''
        git = get_git(path)
        with OriginalBranch(git):
            branches = get_unmerged_remote_branches(git)
            config = BranchConfig(
                branches=branches,
                submodules={
                    submodule: _make_full_config(
                        path_prefix + submodule
                    )
                    for submodule in git_submodules(git)
                }
            )
            return config
    config = _make_full_config(path)
    config.trunk = 'master'
    config.normalize()
    return config


if __name__ == '__main__':
    config = make_full_config()
    check_merges(config, print_details=False)
