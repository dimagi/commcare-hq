import sh
from gitutils import get_git, git_submodules, OriginalBranch
from rebuildstaging import BranchConfig, check_merges


def get_remote_branches(origin, git=None):
    git = git or get_git()
    branches = [
        line.strip().replace('origin/HEAD -> ', '')[len(origin) + 1:]
        for line in
        sh.grep(
            git.branch('--remote'), r'^  {}'.format(origin)
        ).strip().split('\n')
    ]
    return branches


def make_full_config(origin='origin', path=None):
    def _make_full_config(path):
        path_prefix = '{}/'.format(path) if path else ''
        git = get_git(path)
        with OriginalBranch(git):
            branches = get_remote_branches(origin, git=git)
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
