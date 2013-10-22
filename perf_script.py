#!/usr/bin/env python

from django.core.management import execute_manager, setup_environ
import sys, os

filedir = os.path.dirname(__file__)

submodules_list = os.listdir(os.path.join(filedir, 'submodules'))
for d in submodules_list:
    if d == "__init__.py" or d == '.' or d == '..':
        continue
    sys.path.insert(1, os.path.join(filedir, 'submodules', d))

sys.path.append(os.path.join(filedir,'submodules'))

import settings
setup_environ(settings)

from loadtest.fake_data import fake_it
