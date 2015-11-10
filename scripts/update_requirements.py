import fileinput
import subprocess


def reset_branch():
    subprocess.Popen(
        ['git', 'checkout', 'requirements-updater'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def new_packages():
    for line in subprocess.Popen(
        ['pip', 'list', '--outdated'],
        stdout=subprocess.PIPE,
    ).communicate()[0].splitlines():
        parts = line.split()
        package = parts[0]
        new_version = parts[4]
        yield package, new_version

reset_branch()
for package, new_version in new_packages():
    reset_branch()
    updated_branch = 'update-%s_%s' % (package, new_version)
    subprocess.Popen(
        [
            'git',
            'checkout',
            '-b',
            updated_branch,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).communicate()

    print '  - %s' % updated_branch

    for line in fileinput.FileInput('requirements/requirements.txt', inplace=1):
        if line.startswith(package):
            line = '%s==%s' % (package, new_version)
        print line,

    subprocess.Popen(
        ['git', 'commit', '-am', 'update %s to version %s' % (package, new_version)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

reset_branch()
