"""
This file is meant to be used in the following manner:

$ python make_rebuild_staging.py < staging.yaml > rebuildstaging-tmp.sh; bash rebuildstaging-tmp.sh

Where staging.yaml looks as follows:

    trunk: master
    name: autostaging
    branches:
      - feature1
      - feature2
    submodules:
      submodules/module1:
        branches:
          - feature1
      submodules/module2:
        trunk: develop
        branches:
          - feature2

When not specified, a submodule's trunk and name inherit from the parent
"""


def make_rebuild_staging_commands(trunk, name, branches, submodules=None):
    print """trap 'last_status=$?; last_command=$current_command; current_command=$BASH_COMMAND; echo \[`pwd`\] "$last_command"; if [ $last_status -ne 0 ]; then read -p "<enter> to continue; ^Z to fix error and fg to return: "; fi' debug"""
    print 'BASE_PATH=`pwd`'
    _make_rebuild_staging_commands(trunk, name, branches, submodules)


def _make_rebuild_staging_commands(trunk, name, branches, submodules=None,
                                   path=()):
    submodules = submodules or {}
    for submodule, info in submodules.items():
        print 'cd $BASE_PATH'
        for element in path:
            print 'cd {0}'.format(element)
        print 'cd {submodule}'.format(submodule=submodule)
        print 'echo "Rebuilding {submodule}"'.format(submodule=submodule)
        _make_rebuild_staging_commands(
            trunk=info.get('trunk', trunk),
            name=info.get('name', name),
            branches=info['branches'],
            submodules=info.get('submodules'),
            path=path + (submodule,)
        )
    print 'cd $BASE_PATH'
    for element in path:
        print 'cd {0}'.format(element)
    print 'git checkout {trunk}'.format(trunk=trunk)
    print '# git pull origin {trunk}'.format(trunk=trunk)
    for branch in branches:
        print 'git checkout {branch}'.format(branch=branch)
        print '# git pull origin {branch}'.format(branch=branch)
        print ("if [[ -n $(git merge-tree $(git merge-base {trunk} {branch}) {trunk} {branch} | grep '>>>') ]]; "
               "then git merge {trunk}; fi").format(trunk=trunk, branch=branch)
    print 'git checkout -B {name} {trunk}'.format(name=name, trunk=trunk)
    for branch in branches:
        print 'git merge {branch} --no-edit'.format(branch=branch)
    if submodules:
        for submodule in submodules:
            print 'git add {submodule}'.format(submodule=submodule)
        print 'git commit -m "update submodule refs" --no-edit'
    print 'git push origin {name} -f'.format(name=name)


if __name__ == '__main__':
    from sys import stdin
    import yaml
    config = yaml.load(stdin)
    make_rebuild_staging_commands(**config)
