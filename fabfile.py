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
print("We now do deploys from the commcarehq-ansible directory or the control machine.")
print()
time.sleep(2)
if 'y' == input('Do you want instructions for how to migrate? [y/N]'):
    print()
    ansible_repo = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'commcarehq-ansible'))
    if not os.path.isdir(os.path.join(ansible_repo, '.git')):
        if 'y' != input('Do you have a local commcarehq-ansible repository already? [y/N]'):
            print("""
    Set up commcarehq-ansible
    =========================

    Put the commcarehq-ansible repo alongside this one like so:

      cd ..
      git clone https://github.com/dimagi/commcarehq-ansible.git
      cd commcarehq-ansible

    Now make a virtualenv for ansible:

      mkvirtualenv ansible

""")
        else:
            print("""
    Link commcarehq-ansible repo
    ============================

    Symlink your commcarehq-ansible repo so that it lives alongside this one:

      ln -s <path/to/commcarehq-ansible> {ansible_repo}

    When you have done that, run

      fab

    to see more instructions.
""".format(ansible_repo=ansible_repo))
            exit(1)
    else:
        print("✓ You already have the commcarehq-ansible repo alonside this one: {}"
              .format(ansible_repo))
        print()
        time.sleep(1)
    print("""
    Make your ansible environment fab-ready
    =======================================

    Enter the commcarehq-ansible repo and make sure you have the latest

      cd ../commcarehq-ansible
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
    and enter the commcarehq-ansible directory before you will be able to run a fab command.
""")
exit(1)
