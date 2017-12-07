from __future__ import print_function
from __future__ import absolute_import
import argparse
import sh
import yaml
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


def subtract_branch_config(config_1, config_2):
    for branch_2 in config_2.branches:
        if branch_2 in config_1.branches:
            config_1.branches.remove(branch_2)
    for submodule_2, subconfig_2 in config_2.submodules.items():
        subtract_branch_config(config_1.submodules[submodule_2], subconfig_2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'command',
        nargs='?',
        default='check'
    )
    parser.add_argument(
        '--config',
        help='yaml config of remote branches to test'
    )
    parser.add_argument(
        '--exclude',
        help='yaml config branches to exclude from the merge testing'
    )
    args = parser.parse_args()
    if args.config:
        config = BranchConfig(yaml.load(open(args.config)))
    else:
        config = make_full_config()
    if args.exclude:
        exclude_config = BranchConfig(yaml.load(open(args.exclude)))
        subtract_branch_config(config, exclude_config)
    if args.command == 'check':
        check_merges(config, print_details=False)
    elif args.command == 'remote-branches':
        print(yaml.safe_dump(config.to_json()))
