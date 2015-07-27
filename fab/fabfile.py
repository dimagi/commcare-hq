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
        (i.e. ~/www/staging/logs and ~/www/production/logs).
"""
import datetime
import json
import os
import posixpath
import sh
import sys
import time
from collections import defaultdict
from distutils.util import strtobool

from fabric import utils
from fabric.api import run, roles, execute, task, sudo, env, parallel
from fabric.colors import blue
from fabric.context_managers import settings, cd, shell_env
from fabric.contrib import files, console
from fabric.operations import require, local, prompt
import yaml


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
env.linewise = True
env.colorize_errors = True

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
        'log_dir',
        'sudo_user',
        'host_string',
        'project',
        'es_endpoint',
        'jython_home',
        'virtualenv_root',
        'django_port',
        'django_bind',
        'flower_port',
    ]

    host = current_env.get('host_string')
    if host in current_env.get('new_relic_enabled', []):
        ret['new_relic_command'] = '%(virtualenv_root)s/bin/newrelic-admin run-program ' % env
        ret['supervisor_env_vars'] = 'NEW_RELIC_CONFIG_FILE=../newrelic.ini,NEW_RELIC_ENVIRONMENT=%(environment)s' % env
    else:
        ret['new_relic_command'] = ''
        ret['supervisor_env_vars'] = ''

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
    env.code_root = posixpath.join(env.root, 'code_root')
    env.code_root_preindex = posixpath.join(env.root, 'code_root_preindex')
    env.project_root = posixpath.join(env.code_root, env.project)
    env.project_media = posixpath.join(env.code_root, 'media')
    env.virtualenv_root = posixpath.join(env.root, 'python_env')
    env.virtualenv_root_preindex = posixpath.join(env.root, 'python_env_preindex')
    env.services = posixpath.join(env.home, 'services')
    env.jython_home = '/usr/local/lib/jython'
    env.db = '%s_%s' % (env.project, env.environment)


@task
def _set_apache_user():
    if what_os() == 'ubuntu':
        env.apache_user = 'www-data'
    elif what_os() == 'redhat':
        env.apache_user = 'apache'


@roles('lb')
def setup_apache_dirs():
    sudo('mkdir -p %(services)s/apache' % env)


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
@roles(ROLES_ALL_SRC)
def install_packages():
    """Install packages, given a list of package names"""
    _require_target()

    if what_os() == 'ubuntu':
        packages_list = 'apt-packages.txt'
        installer_command = 'apt-get install -y'
    else:
        return

    packages_file = posixpath.join(PROJECT_ROOT, 'requirements', packages_list)

    with open(packages_file) as f:
        packages = f.readlines()

    sudo("%s %s" % (installer_command,
                    " ".join(map(lambda x: x.strip('\n\r'), packages))), user='root')


@task
@roles(ROLES_ALL_SRC)
def install_npm_packages():
    """Install required NPM packages for server"""
    with cd(os.path.join(env.code_root, 'submodules/touchforms-src/touchforms')):
        with shell_env(HOME=env.home):
            sudo("npm install")


@task
@roles(ROLES_ALL_SRC)
@parallel
def upgrade_packages():
    """
    Bring all the installed packages up to date.
    This is a bad idea in RedHat as it can lead to an
    OS Upgrade (e.g RHEL 5.1 to RHEL 6).
    Should be avoided.  Run install packages instead.
    """
    _require_target()
    if what_os() == 'ubuntu':
        sudo("apt-get update", shell=False, user='root')
        sudo("apt-get upgrade -y", shell=False, user='root')
    else:
        return


@task
def what_os():
    with settings(warn_only=True):
        _require_target()
        if getattr(env, 'host_os_map', None) is None:
            # prior use case of setting a env.remote_os
            # did not work when doing multiple hosts with different os!
            # Need to keep state per host!
            env.host_os_map = defaultdict(lambda: '')
        if env.host_os_map[env.host_string] == '':
            print 'Testing operating system type...'
            if (files.exists('/etc/lsb-release',verbose=True) and
                    files.contains(text='DISTRIB_ID=Ubuntu', filename='/etc/lsb-release')):
                remote_os = 'ubuntu'
                print ('Found lsb-release and contains "DISTRIB_ID=Ubuntu", '
                       'this is an Ubuntu System.')
            elif files.exists('/etc/redhat-release', verbose=True):
                remote_os = 'redhat'
                print 'Found /etc/redhat-release, this is a RedHat system.'
            else:
                print 'System OS not recognized! Aborting.'
                exit()
            env.host_os_map[env.host_string] = remote_os
        return env.host_os_map[env.host_string]


@roles(ROLES_ALL_SRC)
@task
def setup_server():
    """Set up a server for the first time in preparation for deployments."""
    _require_target()
    # Install required system packages for deployment, plus some extras
    # Install pip, and use it to install virtualenv
    install_packages()
    sudo("easy_install -U pip")
    sudo("pip install -U virtualenv")
    upgrade_packages()
    execute(create_pg_user)
    execute(create_pg_db)


@roles(ROLES_DB_ONLY)
@task
def create_pg_user():
    """Create the Postgres user"""
    _require_target()
    sudo('createuser -D -R -P -s  %(sudo_user)s' % env, user='postgres')


@roles(ROLES_DB_ONLY)
@task
def create_pg_db():
    """Create the Postgres database"""
    _require_target()
    sudo('createdb -O %(sudo_user)s %(db)s' % env, user='postgres')


@task
def bootstrap():
    """Initialize remote host environment (virtualenv, deploy, update)

    Use it with a targeted -H <hostname> you want to bootstrap for django worker use.
    """
    _require_target()
    sudo('mkdir -p %(root)s' % env, shell=False)
    clone_repo()

    update_code()
    create_virtualenvs()
    update_virtualenv()
    setup_dirs()

    # copy localsettings if it doesn't already exist in case any management
    # commands we want to run now would error otherwise
    with cd(env.code_root):
        sudo('cp -n localsettings.example.py localsettings.py',
             user=env.sudo_user)
    with cd(env.code_root_preindex):
        sudo('cp -n localsettings.example.py localsettings.py',
             user=env.sudo_user)


@task
def unbootstrap():
    """Delete cloned repos and virtualenvs"""

    require('code_root', 'code_root_preindex', 'virtualenv_root',
            'virtualenv_root_preindex')

    with settings(warn_only=True):
        sudo(('rm -rf %(virtualenv_root)s %(virtualenv_root_preindex)s'
              '%(code_root)s %(code_root_preindex)s') % env)


@roles(ROLES_ALL_SRC)
def create_virtualenvs():
    """set up virtualenv on remote host"""
    require('virtualenv_root', 'virtualenv_root_preindex',
            provided_by=('staging', 'production', 'india'))

    args = '--distribute --no-site-packages'
    sudo('cd && virtualenv %s %s' % (args, env.virtualenv_root), shell=True)
    sudo('cd && virtualenv %s %s' % (args, env.virtualenv_root_preindex), shell=True)


@roles(ROLES_ALL_SRC)
def clone_repo():
    """clone a new copy of the git repository"""
    with settings(warn_only=True):
        with cd(env.root):
            exists_results = sudo('ls -d %(code_root)s' % env)
            if exists_results.strip() != env['code_root']:
                sudo('git clone %(code_repo)s %(code_root)s' % env)

            if not files.exists(env.code_root_preindex):
                sudo('git clone %(code_repo)s %(code_root_preindex)s' % env)


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
    execute(_remove_submodule_source_preindex, path)


@roles(ROLES_ALL_SRC)
@parallel
def _remove_submodule_source_main(path):
    with cd(env.code_root):
        sudo('rm -rf submodules/%s' % path)


@roles(ROLES_DB_ONLY)
@parallel
def _remove_submodule_source_preindex(path):
    with cd(env.code_root_preindex):
        sudo('rm -rf submodules/%s' % path)


@task
@roles(ROLES_DB_ONLY)
def preindex_views():
    if not env.should_migrate:
        utils.abort((
            'Skipping preindex_views for "%s" because should_migrate = False'
        ) % env.environment)

    with cd(env.code_root_preindex):
        # update the codebase of the preindex dir
        update_code(preindex=True)
        # no update to env - the actual deploy will do
        # this may break if a new dependency is introduced in preindex
        update_virtualenv(preindex=True)

        sudo((
            'echo "%(virtualenv_root_preindex)s/bin/python '
            '%(code_root_preindex)s/manage.py preindex_everything '
            '8 %(user)s" --mail | at -t `date -d "5 seconds" '
            '+%%m%%d%%H%%M.%%S`'
        ) % env)
        version_static(preindex=True)


@roles(ROLES_ALL_SRC)
@parallel
def update_code(preindex=False):
    if preindex:
        root_to_use = env.code_root_preindex
    else:
        root_to_use = env.code_root

    with cd(root_to_use):
        sudo('git remote prune origin')
        sudo('git fetch')
        sudo("git submodule foreach 'git fetch'")
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
    with cd(env.code_root):
        sudo((
            '%(virtualenv_root)s/bin/python manage.py '
            'record_deploy_success --user "%(user)s" --environment '
            '"%(environment)s" --url %(url)s --mail_admins'
        ) % {
            'virtualenv_root': env.virtualenv_root,
            'user': env.user,
            'environment': env.environment,
            'url': url,
        })


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
        execute(update_code)
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
def deploy():
    """deploy code to remote host by checking out the latest via git"""
    _require_target()
    user_confirm = (
        _confirm_translated() and
        console.confirm("Hey girl, you sure you didn't mean to run AWESOME DEPLOY?", default=False) and
        console.confirm('Are you sure you want to deploy to {env.environment}?'.format(env=env), default=False) and
        console.confirm('Did you run "fab {env.environment} preindex_views"?'.format(env=env), default=False)
    )
    if not user_confirm:
        utils.abort('Deployment aborted.')

    run('echo ping!')  # workaround for delayed console response
    _deploy_without_asking()


def _deploy_without_asking():
    try:
        _execute_with_timing(update_code)
        _execute_with_timing(update_virtualenv)
        _execute_with_timing(install_npm_packages)
        _execute_with_timing(update_touchforms)

        # handle static files
        _execute_with_timing(version_static)
        _execute_with_timing(_do_collectstatic)
        _execute_with_timing(_do_compress)
        # initial update of manifest to make sure we have no
        # Offline Compression Issues as services restart
        _execute_with_timing(update_manifest, soft=True)

        _execute_with_timing(clear_services_dir)
        set_supervisor_config()

        do_migrate = env.should_migrate
        if do_migrate:
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
    except Exception:
        _execute_with_timing(mail_admins, "Deploy failed", "You had better check the logs.")
        # hopefully bring the server back to life
        _execute_with_timing(services_restart)
        raise
    else:
        _execute_with_timing(services_restart)
        url = _tag_commit()
        _execute_with_timing(record_successful_deploy, url)


@task
def force_update_static():
    _require_target()
    execute(_do_collectstatic)
    execute(_do_compress)
    execute(update_manifest)
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


@task
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

    max_wait = datetime.timedelta(minutes=5)
    pause_length = datetime.timedelta(seconds=5)

    _execute_with_timing(preindex_views)

    start = datetime.datetime.utcnow()

    @roles(ROLES_DB_ONLY)
    def preindex_complete():
        with settings(warn_only=True):
            return sudo(
                '%(virtualenv_root_preindex)s/bin/python '
                '%(code_root_preindex)s/manage.py preindex_everything '
                '--check' % env,
                user=env.sudo_user,
            ).succeeded

    done = False
    while not done and datetime.datetime.utcnow() - start < max_wait:
        time.sleep(pause_length.seconds)
        if preindex_complete():
            done = True
        pause_length *= 2

    if done:
        _deploy_without_asking()
    else:
        mail_admins(
            " You can't deploy yet",
            ("Preindexing is taking a while, so hold tight "
             "and wait for an email saying it's done. "
             "Thank you for using AWESOME DEPLOY.")
        )


@task
@roles(ROLES_ALL_SRC)
def update_touchforms():
    # npm bin allows you to specify the locally installed version instead of having to install grunt globally
    with cd(os.path.join(env.code_root, 'submodules/touchforms-src/touchforms')):
        sudo('PATH=$(npm bin):$PATH grunt build --force')


@task
@roles(ROLES_ALL_SRC)
@parallel
def update_virtualenv(preindex=False):
    """
    update external dependencies on remote host

    assumes you've done a code update

    """
    _require_target()
    if preindex:
        root_to_use = env.code_root_preindex
        env_to_use = env.virtualenv_root_preindex
    else:
        root_to_use = env.code_root
        env_to_use = env.virtualenv_root
    requirements = posixpath.join(root_to_use, 'requirements')
    with cd(root_to_use):
        cmd_prefix = 'export HOME=/home/%s && source %s/bin/activate && ' % (
            env.sudo_user, env_to_use)
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


@roles('lb')
def configtest():
    """test Apache configuration"""
    _require_target()
    sudo('apache2ctl configtest', user='root')


@roles('lb')
def apache_reload():
    """reload Apache on remote host"""
    _require_target()
    if what_os() == 'redhat':
        sudo('/etc/init.d/httpd reload')
    elif what_os() == 'ubuntu':
        sudo('/etc/init.d/apache2 reload', user='root')


@roles('lb')
def apache_restart():
    """restart Apache on remote host"""
    _require_target()
    sudo('/etc/init.d/apache2 restart', user='root')

@task
def netstat_plnt():
    """run netstat -plnt on a remote host"""
    _require_target()
    sudo('netstat -plnt', user='root')


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
        sudo('%(virtualenv_root)s/bin/python manage.py syncdb --noinput' % env)
        sudo('%(virtualenv_root)s/bin/python manage.py migrate --noinput' % env)


@task
@roles(ROLES_DB_ONLY)
def migrate():
    """run south migration on remote environment"""
    if not console.confirm(
            'Are you sure you want to run south migrations on '
            '{env.environment}? '
            'You must preindex beforehand. '.format(env=env), default=False):
        utils.abort('Task aborted.')
    _require_target()
    execute(stop_pillows)
    execute(stop_celery_tasks)
    with cd(env.code_root_preindex):
        sudo(
            '%(virtualenv_root_preindex)s/bin/python manage.py migrate --noinput ' % env
            + env.get('app', ''),
            user=env.sudo_user
        )
    _supervisor_command('start all')


@roles(ROLES_DB_ONLY)
def flip_es_aliases():
    """Flip elasticsearch aliases to the latest version"""
    _require_target()
    with cd(env.code_root):
        sudo('%(virtualenv_root)s/bin/python manage.py ptop_es_manage --flip_all_aliases' % env)


@parallel
@roles(ROLES_STATIC)
def _do_compress():
    """Run Django Compressor after a code update"""
    with cd(env.code_root):
        sudo('%(virtualenv_root)s/bin/python manage.py compress --force' % env)
    update_manifest(save=True)


@parallel
@roles(ROLES_STATIC)
def _do_collectstatic():
    """Collect static after a code update"""
    with cd(env.code_root):
        sudo('%(virtualenv_root)s/bin/python manage.py collectstatic --noinput' % env)
        sudo('%(virtualenv_root)s/bin/python manage.py fix_less_imports_collectstatic' % env)


@roles(ROLES_DJANGO)
@parallel
def update_manifest(save=False, soft=False):
    """
    Puts the manifest.json file with the references to the compressed files
    from the proxy machines to the web workers. This must be done on the WEB WORKER, since it
    governs the actual static reference.

    save=True saves the manifest.json file to redis, otherwise it grabs the
    manifest.json file from redis and inserts it into the staticfiles dir.
    """
    withpath = env.code_root
    venv = env.virtualenv_root

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
def version_static(preindex=False):
    """
    Put refs on all static references to prevent stale browser cache hits when things change.
    This needs to be run on the WEB WORKER since the web worker governs the actual static
    reference.

    """

    if preindex:
        withpath = env.code_root_preindex
        venv = env.virtualenv_root_preindex
    else:
        withpath = env.code_root
        venv = env.virtualenv_root

    cmd = 'resource_static' if not preindex else 'resource_static clear'
    with cd(withpath):
        sudo('rm -f tmp.sh resource_versions.py; {venv}/bin/python manage.py {cmd}'.format(venv=venv, cmd=cmd),
            user=env.sudo_user
        )


@task
@roles(ROLES_STATIC)
def collectstatic():
    """run collectstatic on remote environment"""
    _require_target()
    update_code()
    _do_collectstatic()
    _do_compress()
    update_manifest(save=True)


@task
def reset_local_db():
    """Reset local database from remote host"""
    _require_target()
    if env.environment == 'production':
        utils.abort('Local DB reset is for staging environment only')
    question = ('Are you sure you want to reset your local '
                'database with the %(environment)s database?' % env)
    sys.path.append('.')
    if not console.confirm(question, default=False):
        utils.abort('Local database reset aborted.')
    local_db = loc['default']['NAME']
    remote_db = remote['default']['NAME']
    with settings(warn_only=True):
        local('dropdb %s' % local_db)
    local('createdb %s' % local_db)
    host = '%s@%s' % (env.user, env.hosts[0])
    local('ssh -C %s sudo -u commcare-hq pg_dump -Ox %s | psql %s' % (host, remote_db, local_db))


@task
def fix_locale_perms():
    """Fix the permissions on the locale directory"""
    _require_target()
    _set_apache_user()
    locale_dir = '%s/locale/' % env.code_root
    sudo('chown -R %s %s' % (env.sudo_user, locale_dir))
    sudo('chgrp -R %s %s' % (env.apache_user, locale_dir))
    sudo('chmod -R g+w %s' % locale_dir)


@task
def commit_locale_changes():
    """Commit locale changes on the remote server and pull them in locally"""
    fix_locale_perms()
    with cd(env.code_root):
        sudo('-H -u %s git add commcare-hq/locale' % env.sudo_user)
        sudo('-H -u %s git commit -m "updating translation"' % env.sudo_user)
    local('git pull ssh://%s%s' % (env.host, env.code_root))


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
    """Upload and link Supervisor configuration from the template."""
    _require_target()
    _execute_with_timing(set_celery_supervisorconf)
    _execute_with_timing(set_djangoapp_supervisorconf)
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


@task
def update_apache_conf():
    require('code_root', 'django_port')

    with cd(env.code_root):
        tmp = "/tmp/cchq"
        sudo('%s/bin/python manage.py mkapacheconf %s > %s'
              % (env.virtualenv_root, env.django_port, tmp))
        sudo('cp -f %s /etc/apache2/sites-available/cchq' % tmp, user='root')

    with settings(warn_only=True):
        sudo('a2dissite 000-default', user='root')
        sudo('a2dissite default', user='root')

    sudo('a2enmod proxy_http', user='root')
    sudo('a2ensite cchq', user='root')
    sudo('service apache2 reload', user='root')

@task
def update_translations():
    do_update_translations()


@roles(ROLES_PILLOWTOP)
def stop_pillows():
    _require_target()
    with cd(env.code_root):
        sudo('scripts/supervisor-group-ctl stop pillowtop')


@roles(ROLES_CELERY)
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

# tests
@task
def selenium_test():
    _require_target()
    prompt("Jenkins username:", key="jenkins_user", default="selenium")
    prompt("Jenkins password:", key="jenkins_password")
    url = env.selenium_url % {"token": "foobar", "environment": env.environment}
    local("curl --user %(user)s:%(pass)s '%(url)s'" % {
        'user': env.jenkins_user,
        'pass': env.jenkins_password,
        'url': url,
    })
