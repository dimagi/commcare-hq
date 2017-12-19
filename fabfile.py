# coding: utf-8
from __future__ import print_function
from __future__ import unicode_literals
import os
import time

print()
print("Hey things have changed.")
print()
time.sleep(1)
print("We now do deploys from the commcarehq-ansible directory or the control machine.")
print()
time.sleep(2)
if 'y' == raw_input('Do you want instructions for how to migrate? [y/N]'):
    print()
    ansible_repo = os.path.join(os.path.dirname(__file__), '..', 'commcarehq-ansible')
    if not os.path.isdir(os.path.join(ansible_repo, '.git')):
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
        print("✓ You already have the commcarehq-ansible repo alonside this one: {}".format(os.path.realpath(ansible_repo)))
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

    Enter the fab directory of commcarehq-ansible

      cd commcarehq-ansible/fab

    Run your fab command

      fab production deploy


    Bonus: Run fab from any directory
    =================================

    You will always need to enter the ansible virtualenv to run fab from now on,
    but if you use the following alias, you can run it from anywhere.

      alias fab=fab -f ~/.commcare-cloud/fab/fabfile.py

    to add this to your .bash_profile you can run

      echo "alias fab=fab -f ~/.commcare-cloud/fab/fabfile.py" >> ~/.bash_profile

    Now from anywhere

      # workon ansible
      fab production deploy
""")
exit(1)
