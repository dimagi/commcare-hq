import subprocess

subprocess.Popen(['git', 'checkout', 'master'])

for line in subprocess.Popen(
    ['pip', 'list', '--outdated'],
    stdout=subprocess.PIPE,
).communicate()[0].splitlines():
    parts = line.split()
    package = parts[0]
    new_version = parts[4]

    updated_branch = 'update-%s%s' % (package, new_version)

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

subprocess.Popen(
    ['git', 'checkout', 'master'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
