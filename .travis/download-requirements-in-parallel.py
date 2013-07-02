import sys
import subprocess
from os.path import expanduser

requirements = []

for path in sys.argv[1:]:
    with open(path) as fh:
        for line in fh:
            interesting_bit = line.split('#')[0].strip()
            
            if len(interesting_bit) > 0:
                requirements.append(interesting_bit)
                                

jobs = []

home = expanduser("~")

for requirement in requirements:
    jobs.append(subprocess.Popen(['pip', 'install', '--use-wheel', '--use-mirrors', '--no-install',
                                  '--find-links=%s/wheelhouse' % home, requirement]))

for job in jobs:
    job.wait()

