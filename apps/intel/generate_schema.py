# generates schema_models from manage.py inspectdb output.
import os, re

models = {
    "IntelGrameenMotherRegistration"        : "schema_intel_grameen_safe_motherhood_registration_v0_3",
    "IntelGrameenSafeMotherhoodFollowup"    : "schema_intel_grameen_safe_motherhood_followup_v0_2"
}
cmd = "cd ../.. ; python manage.py inspectdb" # gotta be in manage.py's dir
out = '''
from django.db import models
'''

inspect = os.popen(cmd, 'r').read()

tables = inspect.split("\n\n")

p = re.compile("class .*\(")

for table in tables:
    for model_name in models:
        if models[model_name] in table:
            table = p.sub("class %s(" % model_name, table)
            out += "\n\n" + table + "\n\n"

print out