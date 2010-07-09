# generates schema_models from manage.py inspectdb output.
import os, re

MODELS = {
    "IntelGrameenMotherRegistration"        : "view_intel_grameen_safe_motherhood_registrations",
    "IntelGrameenSafeMotherhoodFollowup"    : "view_intel_grameen_safe_motherhood_followups"
}


cmd = "cd ../.. ; python manage.py inspectdb" # gotta be in manage.py's dir
out = '''
from django.db import models
'''

inspect = os.popen(cmd, 'r').read()
inspect = inspect.replace("id = models.IntegerField()\n", "# id = models.IntegerField()\n")

tables = inspect.split("\n\n")

p = re.compile("class .*\(")

for table in tables:
    for model_name in MODELS:
        if MODELS[model_name] in table:
            table = p.sub("class %s(" % model_name, table)
            out += "\n\n" + table + "\n\n"

print out