from optparse import make_option
from django.core.management.base import LabelCommand
from subprocess import Popen, PIPE
from auditcare.models import AuditEvent

GUNICORN_CMD = 'python manage.py run_gunicorn'

class Command(LabelCommand):
    help = "Slay dangling gunicorn processes with no remorse."
    args = ""
    label = ""

    option_list = LabelCommand.option_list + \
                  (
                      make_option('--makeitso',
                                  action='store_true',
                                  dest='makeitso',
                                  default=False,
                                  help="DO IT"),
                      make_option('--no-remorse',
                                  action='store_true',
                                  dest='no_input',
                                  default=False,
                                  help="I know what I'm doing, no confirmation please."),
                  )

    def check_unicorns(self):
        p = Popen(['pgrep', '-f', GUNICORN_CMD], stdout=PIPE, stderr=PIPE)
        pids = p.stdout.read().strip().split('\n')
        if len(pids) > 0:
            print "Found dangling gunicorn processes: %s" % ','.join(pids)
        else:
            print "No gunicorns found, you're safe now."

    def handle(self, *args, **options):
        if options['makeitso']:
            if options['no_input']:
                do_kill = True
            else:
                check_kill = raw_input(
                    """You sure you want to slay these gunicorn processes???

                    Note, you should only do this when you know supervisorctl is in a stuck state.
                    So, in short, I hope you know what you're doing.

                    Proceed with the slaying? (yes/no) """)
                do_kill = check_kill == "yes"

            if do_kill:
                print "\tProceeding to kill gunicorn processes. You may now restart supervisor processes for django\n"
                pk = Popen(['pkill', '-9', '-f', GUNICORN_CMD], stdout=PIPE, stderr=PIPE)
                AuditEvent.audit_command()
            else:
                print "\tNo slaying...for now"








