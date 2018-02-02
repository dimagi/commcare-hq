# coding: utf-8
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import
from six.moves import input
import os
import time

print()
print("Hey things have changed.")
print()
time.sleep(1)
print("We now do deploys from the commcare-cloud directory or the control machine.")
print()
time.sleep(2)
if 'y' == input('Do you want instructions for how to migrate? [y/N]'):
    print()
    for dir_name in ['commcarehq-ansible', 'commcare-cloud']:

        ansible_repo = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', dir_name))
        ansible_repo_exists = os.path.isdir(os.path.join(ansible_repo, '.git'))
        if ansible_repo_exists:
            break
    else:
        if 'y' != input('Do you have a local commcare-cloud (formerly called commcarehq-ansible) repository already? [y/N]'):
            print("""
    Set up commcare-cloud
    =========================

    Put the commcarehq-ansible repo alongside this one like so:

      cd ..
      git clone https://github.com/dimagi/commcare-cloud.git
      cd commcare-cloud

    Now make a virtualenv for ansible:

      mkvirtualenv ansible

""")
        else:
            print("""
    Link commcare-cloud repo
    ============================

    Symlink your commcare-cloud (or commcarehq-ansible) repo so that it lives alongside this one:

      ln -s <path/to/commcare-cloud> {ansible_repo}

    When you have done that, run

      fab

    to see more instructions.
""".format(ansible_repo=ansible_repo))
            exit(1)
    if ansible_repo_exists:
        print("✓ You already have the commcare-cloud repo alonside this one: {}"
              .format(ansible_repo))
        print()
        time.sleep(1)
    print("""
    Make your ansible environment fab-ready
    =======================================

    Enter the commcare-cloud repo and make sure you have the latest

      cd {ansible_repo}
      git pull

    enter the env

      workon ansible

    do the necessary pip installs

      pip install -r fab/requirements.txt

    and make sure the necessary files are in the right place

      ./control/check_install.sh

    Run a fab command!
    ==================

      fab production deploy

    Remember that in steady state, you will need to workon the ansible virtualenv
    and enter the commcare-cloud directory before you will be able to run a fab command.
""".format(ansible_repo=ansible_repo))
exit(1)
