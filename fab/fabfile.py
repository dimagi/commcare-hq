#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Server layout:
    ~/services/
        This contains two subfolders
            /apache/
            /supervisor/
        which hold the configurations for these applications
        for each environment (staging, production, etc) running on the server.
        Theses folders are included in the global /etc/apache2 and
        /etc/supervisor configurations.

    ~/www/
        This folder contains the code, python environment, and logs
        for each environment (staging, production, etc) running on the server.
        Each environment has its own subfolder named for its evironment
        (i.e. ~/www/staging/log and ~/www/production/log).

    ~/www/<environment>/releases/<YYYY-MM-DD-HH.SS>
        This folder contains a release of commcarehq. Each release has its own virtual environment that can be
        found in `python_env`.

    ~/www/<environment>/current
        This path is a symlink to the release that is being run
        (~/www/<environment>/releases<YYYY-MM-DD-HH.SS>).
"""
import datetime
import json
import os
import posixpath
import sh
import sys
import time
import yaml
from collections import defaultdict
from distutils.util import strtobool

from fabric import utils
from fabric.api import run, roles, execute, task, sudo, env, parallel
from fabric.colors import blue, red
from fabric.context_managers import settings, cd, shell_env
from fabric.contrib import files, console
from fabric.operations import require, local, prompt


ROLES_ALL_SRC = ['pg', 'django_monolith', 'django_app', 'django_celery', 'django_pillowtop', 'formsplayer', 'staticfiles']
ROLES_ALL_SERVICES = ['django_monolith', 'django_app', 'django_celery', 'django_pillowtop', 'formsplayer']
ROLES_CELERY = ['django_monolith', 'django_celery']
ROLES_PILLOWTOP = ['django_monolith', 'django_pillowtop']
ROLES_DJANGO = ['django_monolith', 'django_app']
ROLES_TOUCHFORMS = ['django_monolith', 'formsplayer']
ROLES_STATIC = ['django_monolith', 'staticfiles']
ROLES_SMS_QUEUE = ['django_monolith', 'sms_queue']
ROLES_REMINDER_QUEUE = ['django_monolith', 'reminder_queue']
ROLES_PILLOW_RETRY_QUEUE = ['django_monolith', 'pillow_retry_queue']
ROLES_DB_ONLY = ['pg', 'django_monolith']

if env.ssh_config_path and os.path.isfile(os.path.expanduser(env.ssh_config_path)):
    env.use_ssh_config = True

PROJECT_ROOT = os.path.dirname(__file__)
RSYNC_EXCLUDE = (
    '.DS_Store',
    '.git',
    '*.pyc',
    '*.example',
    '*.db',
    )
RELEASE_RECORD = 'RELEASES.txt'
env.linewise = True
env.colorize_errors = True
env['sudo_prefix'] += '-H '

if not hasattr(env, 'code_branch'):
    print ("code_branch not specified, using 'master'. "
           "You can set it with '--set code_branch=<branch>'")
    env.code_branch = 'master'

env.roledefs = {
    'django_celery': [],
    'django_app': [],
    # for now combined with celery
    'django_pillowtop': [],
    'sms_queue': [],
    'reminder_queue': [],
    'pillow_retry_queue': [],
    # 'django_celery, 'django_app', and 'django_pillowtop' all in one
    # use this ONLY for single server config,
    # otherwise deploy() will run multiple times in parallel causing issues
    'django_monolith': [],

    'formsplayer': [],
    'staticfiles': [],

    # package level configs that are not quite config'ed yet in this fabfile
    'couch': [],
    'pg': [],
    'rabbitmq': [],
    'lb': [],
    # need a special 'deploy' role to make deploy only run once
    'deploy': [],
}


def _require_target():
    require('root', 'code_root', 'hosts', 'environment',
            provided_by=('staging', 'preview', 'production', 'india', 'zambia'))


def format_env(current_env, extra=None):
    """
    formats the current env to be a foo=bar,sna=fu type paring
    this is used for the make_supervisor_conf management command
    to pass current environment to make the supervisor conf files remotely
    instead of having to upload them from the fabfile.

    This is somewhat hacky in that we're going to
    cherry pick the env vars we want and make a custom dict to return
    """
    ret = dict()
    important_props = [
        'environment',
        'code_root',
        'code_current',
        'log_dir',
        'sudo_user',
        'host_string',
        'project',
        'es_endpoint',
        'jython_home',
        'virtualenv_root',
        'virtualenv_current',
        'django_port',
        'django_bind',
        'flower_port',
    ]

    host = current_env.get('host_string')
    if host in current_env.get('new_relic_enabled', []):
        ret['new_relic_command'] = '%(virtualenv_root)s/bin/newrelic-admin run-program ' % env
        ret['supervisor_env_vars'] = {
            'NEW_RELIC_CONFIG_FILE': '%(root)s/newrelic.ini' % env,
            'NEW_RELIC_ENVIRONMENT': '%(environment)s' % env
        }
    else:
        ret['new_relic_command'] = ''
        ret['supervisor_env_vars'] = []

    for prop in important_props:
        ret[prop] = current_env.get(prop, '')

    if extra:
        ret.update(extra)

    return json.dumps(ret)


@task
def _setup_path():
    # using posixpath to ensure unix style slashes.
    # See bug-ticket: http://code.fabfile.org/attachments/61/posixpath.patch
    env.root = posixpath.join(env.home, 'www', env.environment)
    env.log_dir = posixpath.join(env.home, 'www', env.environment, 'log')
    env.releases = posixpath.join(env.root, 'releases')
    env.code_current = posixpath.join(env.root, 'current')
    env.code_root = posixpath.join(env.releases, time.strftime('%Y-%m-%d_%H.%M', time.gmtime(time.time())))
    env.project_root = posixpath.join(env.code_root, env.project)
    env.project_media = posixpath.join(env.code_root, 'media')
    env.virtualenv_current = posixpath.join(env.code_current, 'python_env')
    env.virtualenv_root = posixpath.join(env.code_root, 'python_env')
    env.services = posixpath.join(env.home, 'services')
    env.jython_home = '/usr/local/lib/jython'
    env.db = '%s_%s' % (env.project, env.environment)


@roles(ROLES_ALL_SRC)
def setup_dirs():
    """
    create uploaded media, log, etc. directories (if needed) and make writable

    """
    sudo('mkdir -p %(log_dir)s' % env)
    sudo('chmod a+w %(log_dir)s' % env)
    sudo('mkdir -p %(services)s/supervisor' % env)


def load_env(env_name):
    def get_env_dict(path):
        if os.path.isfile(path):
            with open(path) as f:
                try:
                    return yaml.load(f)
                except Exception:
                    print 'Error in file {}'.format(path)
                    raise
        else:
            raise Exception("Environment file not found: {}".format(path))

    env_dict = get_env_dict(os.path.join('fab', 'environments.yml'))
    env.update(env_dict['base'])
    env.update(env_dict[env_name])


@task
def india():
    env.inventory = os.path.join('fab', 'inventory', 'india')
    load_env('india')
    execute(env_common)


@task
def zambia():
    """Our production server in wv zambia."""
    load_env('zambia')
    env.hosts = ['41.72.118.18']

    _setup_path()

    env.roledefs = {
        'couch': [],
        'pg': [],
        'rabbitmq': [],
        'django_celery': [],
        'sms_queue': [],
        'reminder_queue': [],
        'pillow_retry_queue': [],
        'django_app': [],
        'django_pillowtop': [],
        'formsplayer': [],
        'staticfiles': [],
        'lb': [],
        'deploy': [],

        'django_monolith': ['41.72.118.18'],
    }
    env.roles = ['django_monolith']


@task
def production():
    """www.commcarehq.org"""
    if env.code_branch != 'master':
        branch_message = (
            "Woah there bud! You're using branch {env.code_branch}. "
            "ARE YOU DOING SOMETHING EXCEPTIONAL THAT WARRANTS THIS?"
        ).format(env=env)
        if not console.confirm(branch_message, default=False):
            utils.abort('Action aborted.')

    load_env('production')
    env.inventory = os.path.join('fab', 'inventory', 'production')
    execute(env_common)


@task
def staging():
    """staging.commcarehq.org"""
    if env.code_branch == 'master':
        env.code_branch = 'autostaging'
        print ("using default branch of autostaging. you can override this with --set code_branch=<branch>")

    env.inventory = os.path.join('fab', 'inventory', 'staging')
    load_env('staging')
    execute(env_common)


@task
def preview():
    """
    preview.commcarehq.org

    production data in a safe preview environment on remote host

    """
    env.inventory = os.path.join('fab', 'inventory', 'preview')
    load_env('preview')
    execute(env_common)


def read_inventory_file(filename):
    """
    filename is a path to an ansible inventory file

    returns a mapping of group names ("webworker", "proxy", etc.)
    to lists of hosts (ip addresses)

    """
    from ansible.inventory import InventoryParser

    return {name: [host.name for host in group.get_hosts()]
            for name, group in InventoryParser(filename).groups.items()}


@task
def development():
    """
    Must pass in the 'inventory' env variable,
    which is the path to an ansible inventory file
    and an 'environment' env variable,
    which is the name of the directory to be used under /home/cchq/www/

    Example command:

        fab development awesome_deploy \
        --set inventory=/path/to/commcarehq-ansible/ansible/inventories/development,environment=dev

    """
    load_env('development')
    execute(env_common)


def env_common():
    require('inventory', 'environment')
    servers = read_inventory_file(env.inventory)

    _setup_path()

    proxy = servers['proxy']
    webworkers = servers['webworkers']
    postgresql = servers['postgresql']
    couchdb = servers['couchdb']
    touchforms = servers['touchforms']
    elasticsearch = servers['elasticsearch']
    celery = servers['celery']
    rabbitmq = servers['rabbitmq']
    # if no server specified, just don't run pillowtop
    pillowtop = servers.get('pillowtop', [])

    deploy = servers.get('deploy', servers['postgresql'])[:1]

    env.roledefs = {
        'couch': couchdb,
        'pg': postgresql,
        'rabbitmq': rabbitmq,
        'django_celery': celery,
        'sms_queue': celery,
        'reminder_queue': celery,
        'pillow_retry_queue': celery,
        'django_app': webworkers,
        'django_pillowtop': pillowtop,
        'formsplayer': touchforms,
        'staticfiles': proxy,
        'lb': [],
        # having deploy here makes it so that
        # we don't get prompted for a host or run deploy too many times
        'deploy': deploy,
        # fab complains if this doesn't exist
        'django_monolith': [],
    }
    env.roles = ['deploy']
    env.hosts = env.roledefs['deploy']
    env.supervisor_roles = ROLES_ALL_SRC


@task
def webworkers():
    env.supervisor_roles = ROLES_DJANGO


@task
def remove_submodule_source(path):
    """
    Remove submodule source folder.
    :param path: the name of the submodule source folder

    Example usage:
    > fab realstaging remove_submodule_source:ctable-src

    """
    if not console.confirm(
            ('Are you sure you want to delete submodules/{path} on '
             '{env.environment}?').format(path=path, env=env), default=False):
        utils.abort('Action aborted.')

    _require_target()

    execute(_remove_submodule_source_main, path)


@roles(ROLES_ALL_SRC)
@parallel
def _remove_submodule_source_main(path, use_current_release=False):
    with cd(env.code_root if not use_current_release else env.code_current):
        sudo('rm -rf submodules/%s' % path)


@task
@roles(ROLES_DB_ONLY)
def preindex_views():
    """
    Creates a new release that runs preindex_everything. Clones code from `current` release and updates it.
    """
    setup_release()
    _preindex_views()


def _preindex_views():
    if not env.should_migrate:
        utils.abort((
            'Skipping preindex_views for "%s" because should_migrate = False'
        ) % env.environment)

    with cd(env.code_root):
        sudo((
            'echo "%(virtualenv_root)s/bin/python '
            '%(code_root)s/manage.py preindex_everything '
            '8 %(user)s" --mail | at -t `date -d "5 seconds" '
            '+%%m%%d%%H%%M.%%S`'
        ) % env)
        version_static()



@roles(ROLES_ALL_SRC)
@parallel
def update_code(use_current_release=False):
    # If not updating current release,  we are making a new release and thus have to do cloning
    # we should only ever not make a new release when doing a hotfix deploy
    if not use_current_release:
        if files.exists(env.code_current):
            with cd(env.code_current):
                submodules = sudo("git submodule | awk '{ print $2 }'").split()
        with cd(env.code_root):
            if files.exists(env.code_current):
                local_submodule_clone = []
                for submodule in submodules:
                    local_submodule_clone.append('-c')
                    local_submodule_clone.append(
                        'submodule.{submodule}.url={code_current}/.git/modules/{submodule}'.format(
                            submodule=submodule,
                            code_current=env.code_current
                        )
                    )

                sudo('git clone --recursive {} {}/.git {}'.format(
                    ' '.join(local_submodule_clone),
                    env.code_current,
                    env.code_root
                ))
                sudo('git remote set-url origin {}'.format(env.code_repo))
            else:
                sudo('git clone {} {}'.format(env.code_repo, env.code_root))

    with cd(env.code_root if not use_current_release else env.code_current):
        sudo('git remote prune origin')
        sudo('git fetch origin {}'.format(env.code_branch))
        sudo('git checkout %(code_branch)s' % env)
        sudo('git reset --hard origin/%(code_branch)s' % env)
        sudo('git submodule sync')
        sudo('git submodule update --init --recursive')
        # remove all untracked files, including submodules
        sudo("git clean -ffd")
        # remove all .pyc files in the project
        sudo("find . -name '*.pyc' -delete")


@roles(ROLES_DB_ONLY)
def mail_admins(subject, message):
    with cd(env.code_root):
        sudo((
            '%(virtualenv_root)s/bin/python manage.py '
            'mail_admins --subject "%(subject)s" "%(message)s"'
        ) % {
            'virtualenv_root': env.virtualenv_root,
            'subject': subject,
            'message': message,
        })


@roles(ROLES_DB_ONLY)
def record_successful_deploy(url):
    with cd(env.code_current):
        sudo((
            '%(virtualenv_current)s/bin/python manage.py '
            'record_deploy_success --user "%(user)s" --environment '
            '"%(environment)s" --url %(url)s --mail_admins'
        ) % {
            'virtualenv_current': env.virtualenv_current,
            'user': env.user,
            'environment': env.environment,
            'url': url,
        })


@roles(ROLES_ALL_SRC)
@parallel
def record_successful_release():
    with cd(env.root):
        files.append(RELEASE_RECORD, str(env.code_root), use_sudo=True)


@task
def hotfix_deploy():
    """
    deploy ONLY the code with no extra cleanup or syncing

    for small python-only hotfixes

    """
    if not console.confirm('Are you sure you want to deploy to {env.environment}?'.format(env=env), default=False) or \
       not console.confirm('Did you run "fab {env.environment} preindex_views"? '.format(env=env), default=False) or \
       not console.confirm('HEY!!!! YOU ARE ONLY DEPLOYING CODE. THIS IS NOT A NORMAL DEPLOY. COOL???', default=False):
        utils.abort('Deployment aborted.')

    _require_target()
    run('echo ping!')  # workaround for delayed console response
    try:
        execute(update_code, True)
    except Exception:
        execute(mail_admins, "Deploy failed", "You had better check the logs.")
        # hopefully bring the server back to life
        execute(services_restart)
        raise
    else:
        execute(services_restart)
        url = _tag_commit()
        execute(record_successful_deploy, url)


def _confirm_translated():
    if datetime.datetime.now().isoweekday() != 2 or env.environment != 'production':
        return True
    return console.confirm(
        "It's Tuesday, did you update the translations from transifex? "
        "\n(https://confluence.dimagi.com/display/commcarehq/"
        "Internationalization+and+Localization+-+Transifex+Translations)"
    )


@task
def setup_release():
    _execute_with_timing(create_code_dir)
    _execute_with_timing(update_code)
    _execute_with_timing(update_virtualenv)

    _execute_with_timing(copy_release_files)


def _deploy_without_asking():
    try:
        setup_release()

        _execute_with_timing(_preindex_views)

        max_wait = datetime.timedelta(minutes=5)
        pause_length = datetime.timedelta(seconds=5)
        start = datetime.datetime.utcnow()

        @roles(ROLES_DB_ONLY)
        def preindex_complete():
            with settings(warn_only=True):
                return sudo(
                    '%(virtualenv_root)s/bin/python '
                    '%(code_root)s/manage.py preindex_everything '
                    '--check' % env,
                    user=env.sudo_user,
                ).succeeded

        done = False
        while not done and datetime.datetime.utcnow() - start < max_wait:
            time.sleep(pause_length.seconds)
            if preindex_complete():
                done = True
            pause_length *= 2

        if not done:
            raise PreindexNotFinished()

        # handle static files
        _execute_with_timing(version_static)
        _execute_with_timing(_bower_install)
        _execute_with_timing(_do_collectstatic)
        _execute_with_timing(_do_compress)

        _execute_with_timing(clear_services_dir)
        _set_supervisor_config()

        do_migrate = env.should_migrate
        if do_migrate:

            if execute(_migrations_exist):
                _execute_with_timing(stop_pillows)
                _execute_with_timing(stop_celery_tasks)
            _execute_with_timing(_migrate)
        else:
            print(blue("No migration required, skipping."))
        _execute_with_timing(do_update_translations)
        if do_migrate:
            _execute_with_timing(flip_es_aliases)

        # hard update of manifest.json since we're about to force restart
        # all services
        _execute_with_timing(update_manifest)
        _execute_with_timing(clean_releases)
    except PreindexNotFinished:
        mail_admins(
            " You can't deploy yet",
            ("Preindexing is taking a while, so hold tight "
             "and wait for an email saying it's done. "
             "Thank you for using AWESOME DEPLOY.")
        )
    except Exception:
        _execute_with_timing(mail_admins, "Deploy failed", "You had better check the logs.")
        # hopefully bring the server back to life
        _execute_with_timing(services_restart)
        raise
    else:
        _execute_with_timing(update_current)
        _execute_with_timing(services_restart)
        _execute_with_timing(record_successful_release)
        url = _tag_commit()
        _execute_with_timing(record_successful_deploy, url)


@task
@roles(ROLES_ALL_SRC)
@parallel
def update_current(release=None):
    """
    Updates the current release to the one specified or to the code_root
    """
    if ((not release and not files.exists(env.code_root)) or
            (release and not files.exists(release))):
        utils.abort('About to update current to non-existant release')

    sudo('ln -nfs {} {}'.format(release or env.code_root, env.code_current))


@task
@roles(ROLES_ALL_SRC)
@parallel
def unlink_current():
    """
    Unlinks the current code directory. Use with caution.
    """
    message = 'Are you sure you want to unlink the current release of {env.environment}?'.format(env=env)

    if not console.confirm(message, default=False):
        utils.abort('Deployment aborted.')

    if files.exists(env.code_current):
        sudo('unlink {}'.format(env.code_current))


@task
@roles(ROLES_ALL_SRC)
@parallel
def create_code_dir():
    sudo('mkdir -p {}'.format(env.code_root))


@parallel
@roles(ROLES_ALL_SRC)
def copy_localsettings():
    sudo('cp {}/localsettings.py {}/localsettings.py'.format(env.code_current, env.code_root))


@parallel
@roles(ROLES_TOUCHFORMS)
def copy_tf_localsettings():
    sudo(
        'cp {}/submodules/touchforms-src/touchforms/backend/localsettings.py '
        '{}/submodules/touchforms-src/touchforms/backend/localsettings.py'.format(
            env.code_current, env.code_root
        ))


@parallel
@roles(ROLES_ALL_SRC)
def copy_components():
    if files.exists('{}/bower_components'.format(env.code_current)):
        sudo('cp -r {}/bower_components {}/bower_components'.format(env.code_current, env.code_root))
    else:
        # In the event that the folder doesn't exist, create it so that djangobower doesn't choke
        sudo('mkdir -p {}/bower_components/bower_components'.format(env.code_root))


def copy_release_files():
    execute(copy_localsettings)
    execute(copy_tf_localsettings)
    execute(copy_components)


@task
def rollback():
    """
    Rolls back the servers to the previous release if it exists and is same across servers. Note this will not
    rollback the supervisor services.
    """
    number_of_releases = execute(get_number_of_releases)
    if not all(map(lambda n: n > 1, number_of_releases)):
        print red('Aborting because there are not enough previous releases.')
        exit()

    releases = execute(get_previous_release)

    unique_releases = set(releases.values())
    if len(unique_releases) != 1:
        print red('Aborting because not all hosts would rollback to same release')
        exit()

    unique_release = unique_releases.pop()

    if not unique_release:
        print red('Aborting because release path is empty. '
            'This probably means there are no releases to rollback to.')
        exit()

    if not console.confirm('Do you wish to rollback to release: {}'.format(unique_release), default=False):
        print blue('Exiting.')
        exit()

    exists = execute(ensure_release_exists, unique_release)

    if all(exists.values()):
        print blue('Updating current and restarting services')
        execute(update_current, unique_release)
        execute(services_restart)
        execute(mark_last_release_unsuccessful)
    else:
        print red('Aborting because not all hosts have release')
        exit()


@roles(ROLES_ALL_SRC)
@parallel
def get_number_of_releases():
    with cd(env.root):
        return int(sudo("wc -l {} | awk '{{ print $1 }}'".format(RELEASE_RECORD)))


@roles(ROLES_ALL_SRC)
@parallel
def mark_last_release_unsuccessful():
    # Removes last line from RELEASE_RECORD file
    with cd(env.root):
        sudo("sed -i '$d' {}".format(RELEASE_RECORD))


@roles(ROLES_ALL_SRC)
@parallel
def ensure_release_exists(release):
    return files.exists(release)


@roles(ROLES_ALL_SRC)
@parallel
def get_previous_release():
    # Gets second to last line in RELEASES.txt
    with cd(env.root):
        return sudo('tail -2 {} | head -n 1'.format(RELEASE_RECORD))


@task
@roles(ROLES_ALL_SRC)
@parallel
def clean_releases(keep=3):
    """
    Cleans old and failed deploys from the ~/www/<environment>/releases/ directory
    """
    releases = sudo('ls {}'.format(env.releases)).split()
    current_release = os.path.basename(sudo('readlink {}'.format(env.code_current)))

    to_remove = []
    valid_releases = 0
    with cd(env.root):
        for index, release in enumerate(reversed(releases)):
            if (release == current_release or release == os.path.basename(env.code_root)):
                valid_releases += 1
            elif (files.contains(RELEASE_RECORD, release)):
                valid_releases += 1
                if valid_releases > keep:
                    to_remove.append(release)
            else:
                # cleans all releases that were not successful deploys
                to_remove.append(release)

    if len(to_remove) == len(releases):
        print red('Aborting clean_releases, about to remove every release')
        return

    if os.path.basename(env.code_root) in to_remove:
        print red('Aborting clean_releases, about to remove current release')
        return

    for release in to_remove:
        sudo('rm -rf {}/{}'.format(env.releases, release))


@task
def force_update_static():
    _require_target()
    execute(_do_collectstatic, use_current_release=True)
    execute(_do_compress, use_current_release=True)
    execute(update_manifest, use_current_release=True)
    execute(services_restart)


def _tag_commit():
    sh.git.fetch("origin", env.code_branch)
    deploy_time = datetime.datetime.utcnow()
    tag_name = "{:%Y-%m-%d_%H.%M}-{}-deploy".format(deploy_time, env.environment)
    pattern = "*{}*".format(env.environment)
    last_tag = sh.tail(sh.git.tag("-l", pattern), "-1").strip()
    branch = "origin/{}".format(env.code_branch)
    msg = getattr(env, "message", "")
    msg += "\n{} deploy at {}".format(env.environment, deploy_time.isoformat())
    sh.git.tag(tag_name, "-m", msg, branch)
    sh.git.push("origin", tag_name)
    diff_url = "https://github.com/dimagi/commcare-hq/compare/{}...{}".format(
        last_tag,
        tag_name
    )
    print "Here's a link to the changes you just deployed:\n{}".format(diff_url)
    return diff_url


@task(alias='deploy')
def awesome_deploy(confirm="yes"):
    """preindex and deploy if it completes quickly enough, otherwise abort"""
    _require_target()
    if strtobool(confirm) and (
        not _confirm_translated() or
        not console.confirm(
            'Are you sure you want to preindex and deploy to '
            '{env.environment}?'.format(env=env), default=False)
    ):
        utils.abort('Deployment aborted.')

    if datetime.datetime.now().isoweekday() == 5:
        print('')
        print('┓┏┓┏┓┃')
        print('┛┗┛┗┛┃＼○／')
        print('┓┏┓┏┓┃  /      Friday')
        print('┛┗┛┗┛┃ノ)')
        print('┓┏┓┏┓┃         deploy,')
        print('┛┗┛┗┛┃')
        print('┓┏┓┏┓┃         good')
        print('┛┗┛┗┛┃')
        print('┓┏┓┏┓┃         luck!')
        print('┃┃┃┃┃┃')
        print('┻┻┻┻┻┻')

    _deploy_without_asking()


@roles(ROLES_ALL_SRC)
@parallel
def update_virtualenv():
    """
    update external dependencies on remote host

    assumes you've done a code update

    """
    _require_target()
    requirements = posixpath.join(env.code_root, 'requirements')

    # Optimization if we have current setup (i.e. not the first deploy)
    if files.exists(env.virtualenv_current):
        print 'Cloning virtual env'
        # There's a bug in virtualenv-clone that doesn't allow us to clone envs from symlinks
        current_virtualenv = sudo('readlink -f {}'.format(env.virtualenv_current))
        sudo("virtualenv-clone {} {}".format(current_virtualenv, env.virtualenv_root))

    with cd(env.code_root):
        cmd_prefix = 'export HOME=/home/%s && source %s/bin/activate && ' % (
            env.sudo_user, env.virtualenv_root)
        # uninstall requirements in uninstall-requirements.txt
        # but only the ones that are actually installed (checks pip freeze)
        sudo("%s bash scripts/uninstall-requirements.sh" % cmd_prefix,
             user=env.sudo_user)
        sudo('%s pip install --timeout 60 --requirement %s --requirement %s' % (
            cmd_prefix,
            posixpath.join(requirements, 'prod-requirements.txt'),
            posixpath.join(requirements, 'requirements.txt'),
        ))


@roles(ROLES_ALL_SERVICES)
@parallel
def clear_services_dir():
    """
    remove old confs from directory first
    the clear_supervisor_confs management command will scan the directory and find prefixed conf files of the supervisord files
    and delete them matching the prefix of the current server environment

    """
    services_dir = posixpath.join(env.services, u'supervisor')
    with cd(env.code_root):
        sudo((
            '%(virtualenv_root)s/bin/python manage.py '
            'clear_supervisor_confs --conf_location "%(conf_location)s"'
        ) % {
            'virtualenv_root': env.virtualenv_root,
            'conf_location': services_dir,
        })


@task
def supervisorctl(command):
    require('supervisor_roles',
            provided_by=('staging', 'preview', 'production', 'india', 'zambia'))

    @roles(env.supervisor_roles)
    def _inner():
        _supervisor_command(command)

    execute(_inner)


@roles(ROLES_ALL_SERVICES)
def services_stop():
    """Stop the gunicorn servers"""
    _require_target()
    _supervisor_command('stop all')


@task
def restart_services():
    _require_target()
    if not console.confirm('Are you sure you want to restart the services on '
                           '{env.environment}?'.format(env=env), default=False):
        utils.abort('Task aborted.')

    execute(services_restart)


@roles(ROLES_ALL_SERVICES)
@parallel
def services_restart():
    """Stop and restart all supervisord services"""
    _require_target()
    _supervisor_command('stop all')

    _supervisor_command('update')
    _supervisor_command('reload')
    time.sleep(5)
    _supervisor_command('start  all')


@roles(ROLES_DB_ONLY)
def _migrate():
    """run south migration on remote environment"""
    _require_target()
    with cd(env.code_root):
        sudo('%(virtualenv_root)s/bin/python manage.py sync_finish_couchdb_hq' % env)
        sudo('%(virtualenv_root)s/bin/python manage.py migrate --noinput' % env)


@roles(ROLES_DB_ONLY)
def _migrations_exist():
    """
    Check if there exists database migrations to run
    """
    _require_target()
    with cd(env.code_root):
        n_migrations = int(sudo(
            '%(virtualenv_root)s/bin/python manage.py migrate --list | grep "\[ ]" | wc -l' % env)
        )
        return n_migrations > 0


@roles(ROLES_DB_ONLY)
@parallel
def flip_es_aliases():
    """Flip elasticsearch aliases to the latest version"""
    _require_target()
    with cd(env.code_root):
        sudo('%(virtualenv_root)s/bin/python manage.py ptop_es_manage --flip_all_aliases' % env)


@parallel
@roles(ROLES_STATIC)
def _do_compress(use_current_release=False):
    """Run Django Compressor after a code update"""
    venv = env.virtualenv_root if not use_current_release else env.virtualenv_current
    with cd(env.code_root if not use_current_release else env.code_current):
        sudo('{}/bin/python manage.py compress --force'.format(venv))
    update_manifest(save=True, use_current_release=use_current_release)


@parallel
@roles(ROLES_STATIC)
def _do_collectstatic(use_current_release=False):
    """Collect static after a code update"""
    venv = env.virtualenv_root if not use_current_release else env.virtualenv_current
    with cd(env.code_root if not use_current_release else env.code_current):
        sudo('{}/bin/python manage.py collectstatic --noinput'.format(venv))
        sudo('{}/bin/python manage.py fix_less_imports_collectstatic'.format(venv))


@parallel
@roles(ROLES_STATIC)
def _bower_install(use_current_release=False):
    with cd(env.code_root if not use_current_release else env.code_current):
        sudo('bower install --production')


@roles(ROLES_DJANGO)
@parallel
def update_manifest(save=False, soft=False, use_current_release=False):
    """
    Puts the manifest.json file with the references to the compressed files
    from the proxy machines to the web workers. This must be done on the WEB WORKER, since it
    governs the actual static reference.

    save=True saves the manifest.json file to redis, otherwise it grabs the
    manifest.json file from redis and inserts it into the staticfiles dir.
    """
    withpath = env.code_root if not use_current_release else env.code_current
    venv = env.virtualenv_root if not use_current_release else env.virtualenv_current

    args = ''
    if save:
        args = ' save'
    if soft:
        args = ' soft'
    cmd = 'update_manifest%s' % args
    with cd(withpath):
        sudo('{venv}/bin/python manage.py {cmd}'.format(venv=venv, cmd=cmd),
            user=env.sudo_user
        )


@roles(ROLES_DJANGO)
@parallel
def version_static():
    """
    Put refs on all static references to prevent stale browser cache hits when things change.
    This needs to be run on the WEB WORKER since the web worker governs the actual static
    reference.

    """

    cmd = 'resource_static'
    with cd(env.code_root):
        sudo('rm -f tmp.sh resource_versions.py; {venv}/bin/python manage.py {cmd}'.format(
            venv=env.virtualenv_root, cmd=cmd
        ),
            user=env.sudo_user
        )


def _rebuild_supervisor_conf_file(conf_command, filename, params=None):
    with cd(env.code_root):
        sudo((
            '%(virtualenv_root)s/bin/python manage.py '
            '%(conf_command)s --traceback --conf_file "%(filename)s" '
            '--conf_destination "%(destination)s" --params \'%(params)s\''
        ) % {

            'conf_command': conf_command,
            'virtualenv_root': env.virtualenv_root,
            'filename': filename,
            'destination': posixpath.join(env.services, 'supervisor'),
            'params': format_env(env, params)
        })


def get_celery_queues():
    host = env.get('host_string')
    if host and '.' in host:
        host = host.split('.')[0]

    queues = env.celery_processes.get('*', {})
    host_queues = env.celery_processes.get(host, {})
    queues.update(host_queues)

    return queues

@roles(ROLES_CELERY)
def set_celery_supervisorconf():

    conf_files = {
        'main':                         ['supervisor_celery_main.conf'],
        'periodic':                     ['supervisor_celery_beat.conf', 'supervisor_celery_periodic.conf'],
        'sms_queue':                    ['supervisor_celery_sms_queue.conf'],
        'reminder_queue':               ['supervisor_celery_reminder_queue.conf'],
        'reminder_rule_queue':          ['supervisor_celery_reminder_rule_queue.conf'],
        'reminder_case_update_queue':   ['supervisor_celery_reminder_case_update_queue.conf'],
        'pillow_retry_queue':           ['supervisor_celery_pillow_retry_queue.conf'],
        'background_queue':             ['supervisor_celery_background_queue.conf'],
        'saved_exports_queue':          ['supervisor_celery_saved_exports_queue.conf'],
        'ucr_queue':                    ['supervisor_celery_ucr_queue.conf'],
        'email_queue':                  ['supervisor_celery_email_queue.conf'],
        'logistics_reminder_queue':     ['supervisor_celery_logistics_reminder_queue.conf'],
        'logistics_background_queue':   ['supervisor_celery_logistics_background_queue.conf'],
        'flower':                       ['supervisor_celery_flower.conf'],
        }

    queues = get_celery_queues()
    for queue, params in queues.items():
        for config_file in conf_files[queue]:
            _rebuild_supervisor_conf_file('make_supervisor_conf', config_file, {'celery_params': params})


@roles(ROLES_PILLOWTOP)
def set_pillowtop_supervisorconf():
    # Don't run for preview,
    # and also don't run if there are no hosts for the 'django_pillowtop' role.
    # If there are no matching roles, it's still run once
    # on the 'deploy' machine, db!
    # So you need to explicitly test to see if all_hosts is empty.
    if env.environment not in ['preview'] and env.all_hosts:
        # preview environment should not run pillowtop and index stuff
        # just rely on what's on staging
        _rebuild_supervisor_conf_file('make_supervisor_pillowtop_conf', 'supervisor_pillowtop.conf')


@roles(ROLES_DJANGO)
def set_djangoapp_supervisorconf():
    _rebuild_supervisor_conf_file('make_supervisor_conf', 'supervisor_django.conf')


@roles(ROLES_DJANGO)
def set_errand_boy_supervisorconf():
    _rebuild_supervisor_conf_file('make_supervisor_conf', 'supervisor_errand_boy.conf')


@roles(ROLES_TOUCHFORMS)
def set_formsplayer_supervisorconf():
    _rebuild_supervisor_conf_file('make_supervisor_conf', 'supervisor_formsplayer.conf')

@roles(ROLES_SMS_QUEUE)
def set_sms_queue_supervisorconf():
    if 'sms_queue' in get_celery_queues():
        _rebuild_supervisor_conf_file('make_supervisor_conf', 'supervisor_sms_queue.conf')

@roles(ROLES_REMINDER_QUEUE)
def set_reminder_queue_supervisorconf():
    if 'reminder_queue' in get_celery_queues():
        _rebuild_supervisor_conf_file('make_supervisor_conf', 'supervisor_reminder_queue.conf')

@roles(ROLES_PILLOW_RETRY_QUEUE)
def set_pillow_retry_queue_supervisorconf():
    if 'pillow_retry_queue' in get_celery_queues():
        _rebuild_supervisor_conf_file('make_supervisor_conf', 'supervisor_pillow_retry_queue.conf')


@task
def set_supervisor_config():
    setup_release()
    _set_supervisor_config()


def _set_supervisor_config():
    """Upload and link Supervisor configuration from the template."""
    _require_target()
    _execute_with_timing(set_celery_supervisorconf)
    _execute_with_timing(set_djangoapp_supervisorconf)
    _execute_with_timing(set_errand_boy_supervisorconf)
    _execute_with_timing(set_formsplayer_supervisorconf)
    _execute_with_timing(set_pillowtop_supervisorconf)
    _execute_with_timing(set_sms_queue_supervisorconf)
    _execute_with_timing(set_reminder_queue_supervisorconf)
    _execute_with_timing(set_pillow_retry_queue_supervisorconf)

    # if needing tunneled ES setup, comment this back in
    # execute(set_elasticsearch_supervisorconf)


def _supervisor_command(command):
    _require_target()
    sudo('supervisorctl %s' % (command), shell=False, user='root')


@roles(ROLES_PILLOWTOP)
def stop_pillows():
    _require_target()
    with cd(env.code_root):
        sudo('scripts/supervisor-group-ctl stop pillowtop')


@roles(ROLES_CELERY)
@parallel
def stop_celery_tasks():
    _require_target()
    with cd(env.code_root):
        sudo('scripts/supervisor-group-ctl stop celery')


@roles(ROLES_ALL_SRC)
@parallel
def do_update_translations():
    with cd(env.code_root):
        update_locale_command = '{virtualenv_root}/bin/python manage.py update_django_locales'.format(
            virtualenv_root=env.virtualenv_root,
        )
        update_translations_command = '{virtualenv_root}/bin/python manage.py compilemessages'.format(
            virtualenv_root=env.virtualenv_root,
        )
        sudo(update_locale_command)
        sudo(update_translations_command)


@task
def reset_mvp_pillows():
    _require_target()
    setup_release()
    mvp_pillows = [
        'MVPFormIndicatorPillow',
        'MVPCaseIndicatorPillow',
    ]
    for pillow in mvp_pillows:
        reset_pillow(pillow)


@roles(ROLES_PILLOWTOP)
def reset_pillow(pillow):
    _require_target()
    prefix = 'commcare-hq-{}-pillowtop'.format(env.environment)
    _supervisor_command('stop {prefix}-{pillow}'.format(
        prefix=prefix,
        pillow=pillow
    ))
    with cd(env.code_root):
        command = '{virtualenv_root}/bin/python manage.py ptop_reset_checkpoint {pillow} --noinput'.format(
            virtualenv_root=env.virtualenv_root,
            pillow=pillow,
        )
        sudo(command)
    _supervisor_command('start {prefix}-{pillow}'.format(
        prefix=prefix,
        pillow=pillow
    ))


def _execute_with_timing(fn, *args, **kwargs):
    start_time = datetime.datetime.utcnow()
    execute(fn, *args, **kwargs)
    if env.timing_log:
        with open(env.timing_log, 'a') as timing_log:
            duration = datetime.datetime.utcnow() - start_time
            timing_log.write('{}: {}\n'.format(fn.__name__, duration.seconds))


class PreindexNotFinished(Exception):
    pass
