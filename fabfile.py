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
import os
import posixpath
import sys
import time
from collections import defaultdict
from distutils.util import strtobool

from fabric import utils
from fabric.api import run, roles, execute, task, sudo, env, parallel
from fabric.colors import blue
from fabric.context_managers import settings, cd
from fabric.contrib import files, console
from fabric.operations import require, local, prompt


ROLES_ALL_SRC = ['django_monolith', 'django_app', 'django_celery', 'django_pillowtop', 'formsplayer', 'staticfiles']
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

PROD_PROXIES = [
    'hqproxy0.internal.commcarehq.org',
    'hqproxy3.internal.commcarehq.org',
]


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
env.project = 'commcare-hq'
env.code_repo = 'git://github.com/dimagi/commcare-hq.git'
env.linewise = True

if not hasattr(env, 'code_branch'):
    print ("code_branch not specified, using 'master'. "
           "You can set it with '--set code_branch=<branch>'")
    env.code_branch = 'master'

env.home = "/home/cchq"
env.selenium_url = 'http://jenkins.dimagi.com/job/commcare-hq-post-deploy/buildWithParameters?token=%(token)s&TARGET=%(environment)s'
# Default to safety
env.should_migrate = False
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

env.django_bind = '127.0.0.1'
env.sms_queue_enabled = False
env.reminder_queue_enabled = False
env.reminder_rule_queue_enabled = False
env.reminder_case_update_queue_enabled = False
env.pillow_retry_queue_enabled = True


def _require_target():
    require('root', 'code_root', 'hosts', 'environment',
            provided_by=('staging', 'preview', 'production', 'india', 'zambia'))


def format_env(current_env):
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

    for prop in important_props:
        ret[prop] = current_env.get(prop, '')
    return ','.join(['%s=%s' % (k, v) for k, v in ret.items()])


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



@task
def india():
    """Our production server in India."""
    env.home = '/home/commcarehq/'
    env.environment = 'india'
    env.sudo_user = 'commcarehq'
    env.hosts = ['220.226.209.82']
    env.user = prompt("Username: ", default=env.user)
    env.django_port = '8001'
    env.should_migrate = True

    _setup_path()
    env.virtualenv_root = posixpath.join(
        env.home, '.virtualenvs/commcarehq27')
    env.virtualenv_root_preindex = posixpath.join(
        env.home, '.virtualenvs/commcarehq27_preindex')

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

        'django_monolith': ['220.226.209.82'],
    }
    env.roles = ['django_monolith']
    env.es_endpoint = 'localhost'
    env.flower_port = 5555



@task
def zambia():
    """Our production server in wv zambia."""
    env.sudo_user = 'cchq'
    env.environment = 'production'
    env.django_port = '9010'
    env.code_branch = 'master'
    env.should_migrate = True

    env.hosts = ['41.222.19.153']  # LIKELY THAT THIS WILL CHANGE

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

        'django_monolith': ['41.222.19.153'],
    }
    env.roles = ['django_monolith']
    env.es_endpoint = 'localhost'
    env.flower_port = 5555


@task
def production():
    """www.commcarehq.org"""
    env.sudo_user = 'cchq'
    env.environment = 'production'
    env.django_bind = '0.0.0.0'
    env.django_port = '9010'
    env.should_migrate = True
    env.sms_queue_enabled = True
    env.reminder_queue_enabled = True
    env.reminder_rule_queue_enabled = True
    env.reminder_case_update_queue_enabled = True
    env.pillow_retry_queue_enabled = True

    if env.code_branch != 'master':
        branch_message = (
            "Woah there bud! You're using branch {env.code_branch}. "
            "ARE YOU DOING SOMETHING EXCEPTIONAL THAT WARRANTS THIS?"
        ).format(env=env)
        if not console.confirm(branch_message, default=False):
            utils.abort('Action aborted.')

    class Servers(object):
        db = ['hqdb0.internal.commcarehq.org']
        celery = ['hqcelery1.internal.commcarehq.org']
        touch = ['hqtouch1.internal.commcarehq.org']
        django = ['hqdjango3.internal.commcarehq.org',
                  'hqdjango4.internal.commcarehq.org',
                  'hqdjango5.internal.commcarehq.org']

    env.roledefs = {
        'couch': Servers.db,
        'pg': Servers.db,
        'rabbitmq': Servers.db,
        'django_celery': Servers.celery,
        'sms_queue': Servers.celery,
        'reminder_queue': Servers.celery,
        'pillow_retry_queue': Servers.celery,
        'django_app': Servers.django,
        'django_pillowtop': Servers.db,

        # for now, we'll have touchforms run on both hqdb0 and hqdjango0
        # will remove hqdjango0 once we verify it works well on hqdb0
        'formsplayer': Servers.touch,
        'lb': [],
        'staticfiles': PROD_PROXIES,
        # having deploy here makes it so that
        # we don't get prompted for a host or run deploy too many times
        'deploy': Servers.db,
        # fab complains if this doesn't exist
        'django_monolith': []
    }

    env.server_name = 'commcare-hq-production'
    env.settings = '%(project)s.localsettings' % env
    # e.g. 'ubuntu' or 'redhat'.
    # Gets auto-populated by what_os()
    # if you don't know what it is or don't want to specify.
    env.host_os_map = None

    # The next 2 lines should be commented out when running bootstrap on a new machine
    env.roles = ['deploy']
    env.hosts = env.roledefs['deploy']

    env.es_endpoint = 'hqes0.internal.commcarehq.org'
    env.flower_port = 5555

    _setup_path()


@task
def staging():
    """staging.commcarehq.org"""
    if env.code_branch == 'master':
        env.code_branch = 'autostaging'
        print ("using default branch of autostaging. you can override this with --set code_branch=<branch>")

    env.sudo_user = 'cchq'
    env.environment = 'staging'
    env.django_bind = '0.0.0.0'
    env.django_port = '9010'

    env.should_migrate = True
    # We should not enable the sms queue on staging because replication
    # can cause sms to be processed again if an sms is replicated in its
    # queued state.
    env.sms_queue_enabled = False
    env.pillow_retry_queue_enabled = True

    env.roledefs = {
        'couch': ['hqdb0-staging.internal.commcarehq.org'],
        'pg': ['hqdb0-staging.internal.commcarehq.org'],
        'rabbitmq': ['hqdb0-staging.internal.commcarehq.org'],
        'django_celery': ['hqdb0-staging.internal.commcarehq.org'],
        'sms_queue': ['hqdb0-staging.internal.commcarehq.org'],
        'reminder_queue': ['hqdb0-staging.internal.commcarehq.org'],
        'pillow_retry_queue': ['hqdb0-staging.internal.commcarehq.org'],
        'django_app': ['hqdjango0-staging.internal.commcarehq.org','hqdjango1-staging.internal.commcarehq.org'],
        'django_pillowtop': ['hqdb0-staging.internal.commcarehq.org'],

        'formsplayer': ['hqdjango1-staging.internal.commcarehq.org'],
        'lb': [],
        'staticfiles': PROD_PROXIES,
        'deploy': ['hqdb0-staging.internal.commcarehq.org'],
        # fab complains if this doesn't exist
        'django_monolith': [],
    }

    env.es_endpoint = 'hqdjango1-staging.internal.commcarehq.org'''

    env.server_name = 'commcare-hq-staging'
    env.settings = '%(project)s.localsettings' % env
    env.host_os_map = None
    env.roles = ['deploy']
    env.hosts = env.roledefs['deploy']
    env.flower_port = 5555

    _setup_path()


@task
def realstaging():
    print "(You know you can just use 'staging' now, right? Doing that for ya.)"
    staging()


@task
def preview():
    """
    preview.commcarehq.org

    production data in a safe preview environment on remote host

    """
    env.code_branch = 'master'
    env.sudo_user = 'cchq'
    env.environment = 'preview'
    env.django_bind = '0.0.0.0'
    env.django_port = '7999'
    env.should_migrate = False

    env.sms_queue_enabled = False
    env.pillow_retry_queue_enabled = False

    env.roledefs = {
        'couch': [],
        'pg': [],
        'rabbitmq': ['hqdb0-preview.internal.commcarehq.org'],
        'django_celery': ['hqdb0-preview.internal.commcarehq.org'],
        'sms_queue': ['hqdb0-preview.internal.commcarehq.org'],
        'reminder_queue': ['hqdb0-preview.internal.commcarehq.org'],
        'pillow_retry_queue': ['hqdb0-preview.internal.commcarehq.org'],
        'django_app': [
            'hqdjango0-preview.internal.commcarehq.org',
            'hqdjango1-preview.internal.commcarehq.org'
        ],
        'django_pillowtop': ['hqdb0-preview.internal.commcarehq.org'],

        'formsplayer': ['hqdjango0-preview.internal.commcarehq.org'],
        'lb': [],
        'staticfiles': PROD_PROXIES,
        'deploy': ['hqdb0-preview.internal.commcarehq.org'],
        'django_monolith': [],
    }

    env.es_endpoint = 'hqdjango1-preview.internal.commcarehq.org'''

    env.server_name = 'commcare-hq-preview'
    env.settings = '%(project)s.localsettings' % env
    env.host_os_map = None
    env.roles = ['deploy']
    env.hosts = env.roledefs['deploy']
    env.flower_port = 5556

    _setup_path()


@task
def development():
    """A development monolith target - must specify a host either by command line or prompt"""
    env.sudo_user = 'cchq'
    env.environment = 'development'
    env.django_bind = '0.0.0.0'
    env.django_port = '9010'
    env.should_migrate = True

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

        'django_monolith': env.hosts
    }
    env.roles = ['django_monolith']
    env.es_endpoint = 'localhost'
    env.flower_port = 5555

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
def record_successful_deploy():
    with cd(env.code_root):
        sudo((
            '%(virtualenv_root)s/bin/python manage.py '
            'record_deploy_success --user "%(user)s" --environment '
            '"%(environment)s" --mail_admins'
        ) % {
            'virtualenv_root': env.virtualenv_root,
            'user': env.user,
            'environment': env.environment,
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
        execute(record_successful_deploy)


@task
def deploy():
    """deploy code to remote host by checking out the latest via git"""
    _require_target()
    user_confirm = (
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
        execute(update_code)
        execute(update_virtualenv)

        # handle static files
        execute(version_static)
        execute(_do_collectstatic)
        execute(_do_compress)
        # initial update of manifest to make sure we have no
        # Offline Compression Issues as services restart
        execute(update_manifest, soft=True)

        execute(clear_services_dir)
        set_supervisor_config()

        do_migrate = env.should_migrate and needs_to_migrate()
        if do_migrate:
            execute(stop_pillows)
            execute(stop_celery_tasks)
            execute(_migrate)
        else:
            print(blue("No migration required, skipping."))
        execute(do_update_django_locales)
        if do_migrate:
            execute(flip_es_aliases)

        # hard update of manifest.json since we're about to force restart
        # all services
        execute(update_manifest)
    except Exception:
        execute(mail_admins, "Deploy failed", "You had better check the logs.")
        # hopefully bring the server back to life
        execute(services_restart)
        raise
    else:
        execute(services_restart)
        execute(record_successful_deploy)


@roles(ROLES_DB_ONLY)
def needs_to_migrate():
    with cd(env.code_root):
        result = sudo((
            '%(virtualenv_root)s/bin/python manage.py '
            'migrate --all --merge --list | grep "( )"' % env
        ), quiet=True)
        return result.return_code == 0


@task
def awesome_deploy(confirm="yes"):
    """preindex and deploy if it completes quickly enough, otherwise abort"""
    _require_target()
    if strtobool(confirm) and not console.confirm(
            'Are you sure you want to preindex and deploy to '
            '{env.environment}?'.format(env=env), default=False):
        utils.abort('Deployment aborted.')
    max_wait = datetime.timedelta(minutes=5)
    start = datetime.datetime.utcnow()
    pause_length = datetime.timedelta(seconds=5)

    execute(preindex_views)

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
        sudo('%s pip install --requirement %s --requirement %s' % (
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
    time.sleep(1)
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


def _rebuild_supervisor_conf_file(conf_command, filename):
    with cd(env.code_root):
        sudo((
            '%(virtualenv_root)s/bin/python manage.py '
            '%(conf_command)s --conf_file "%(filename)s" '
            '--conf_destination "%(destination)s" --params "%(params)s"'
        ) % {

            'conf_command': conf_command,
            'virtualenv_root': env.virtualenv_root,
            'filename': filename,
            'destination': posixpath.join(env.services, 'supervisor'),
            'params': format_env(env)
        })


@roles(ROLES_CELERY)
def set_celery_supervisorconf():
    _rebuild_supervisor_conf_file('make_supervisor_conf', 'supervisor_celery_main.conf')

    # hack to not have staging environments send out reminders
    if env.environment not in ['staging', 'preview', 'realstaging']:
        _rebuild_supervisor_conf_file('make_supervisor_conf', 'supervisor_celery_beat.conf')
        _rebuild_supervisor_conf_file('make_supervisor_conf', 'supervisor_celery_periodic.conf')
    if env.sms_queue_enabled:
        _rebuild_supervisor_conf_file('make_supervisor_conf', 'supervisor_celery_sms_queue.conf')
    if env.reminder_queue_enabled:
        _rebuild_supervisor_conf_file('make_supervisor_conf', 'supervisor_celery_reminder_queue.conf')
    if env.reminder_rule_queue_enabled:
        _rebuild_supervisor_conf_file('make_supervisor_conf', 'supervisor_celery_reminder_rule_queue.conf')
    if env.reminder_case_update_queue_enabled:
        _rebuild_supervisor_conf_file('make_supervisor_conf', 'supervisor_celery_reminder_case_update_queue.conf')
    _rebuild_supervisor_conf_file('make_supervisor_conf', 'supervisor_celery_doc_deletion_queue.conf')
    _rebuild_supervisor_conf_file('make_supervisor_conf', 'supervisor_celery_saved_exports_queue.conf')
    _rebuild_supervisor_conf_file('make_supervisor_conf', 'supervisor_celery_flower.conf')
    _rebuild_supervisor_conf_file('make_supervisor_conf', 'supervisor_couchdb_lucene.conf') #to be deprecated


@roles(ROLES_PILLOWTOP)
def set_pillowtop_supervisorconf():
    # in reality this also should be another machine
    # if the number of listeners gets too high
    if env.environment not in ['preview']:
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
    if env.sms_queue_enabled:
        _rebuild_supervisor_conf_file('make_supervisor_conf', 'supervisor_sms_queue.conf')

@roles(ROLES_REMINDER_QUEUE)
def set_reminder_queue_supervisorconf():
    if env.reminder_queue_enabled:
        _rebuild_supervisor_conf_file('make_supervisor_conf', 'supervisor_reminder_queue.conf')

@roles(ROLES_PILLOW_RETRY_QUEUE)
def set_pillow_retry_queue_supervisorconf():
    if env.pillow_retry_queue_enabled:
        _rebuild_supervisor_conf_file('make_supervisor_conf', 'supervisor_pillow_retry_queue.conf')

@task
def set_supervisor_config():
    """Upload and link Supervisor configuration from the template."""
    _require_target()
    execute(set_celery_supervisorconf)
    execute(set_djangoapp_supervisorconf)
    execute(set_formsplayer_supervisorconf)
    execute(set_pillowtop_supervisorconf)
    execute(set_sms_queue_supervisorconf)
    execute(set_reminder_queue_supervisorconf)
    execute(set_pillow_retry_queue_supervisorconf)

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
def update_django_locales():
    do_update_django_locales()


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
def do_update_django_locales():
    with cd(env.code_root):
        command = '{virtualenv_root}/bin/python manage.py update_django_locales'.format(
            virtualenv_root=env.virtualenv_root,
        )
        sudo(command)

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
