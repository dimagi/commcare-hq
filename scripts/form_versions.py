# #!/usr/bin/env python

# from django.core.management import execute_manager, setup_environ
# import sys, os

# filedir = os.path.dirname(__file__)

# submodules_list = os.listdir(os.path.join(filedir, 'submodules'))
# for d in submodules_list:
    # if d == "__init__.py" or d == '.' or d == '..':
        # continue
    # sys.path.insert(1, os.path.join(filedir, 'submodules', d))

# sys.path.append(os.path.join(filedir,'submodules'))

# import settings

# setup_environ(settings)

# ######################################

from corehq.apps.app_manager.models import SavedAppBuild, Application


def run():
    builds = True
    limit = 100
    skip = 0
    while builds:
        builds = Application.view(
            'app_manager/builds_by_date',
            include_docs=True,
            reduce=False,
            limit=limit,
            skip=skip,
            reverse=True
        ).all()
        skip += limit
        for build in builds:
            if any([
                form.version > build.version
                for module in build.modules
                for form in module.forms
            ]):
                print build._id
