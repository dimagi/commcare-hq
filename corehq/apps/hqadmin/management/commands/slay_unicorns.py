from optparse import make_option
from django.core.management.base import LabelCommand
from subprocess import Popen, PIPE
from auditcare.models import AuditEvent
from django.conf import settings

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
                      make_option('--aggressive',
                                  action='store_true',
                                  dest='aggressive',
                                  default=False,
                                  help="Don't use supervisorctl"),
                      make_option('--no-remorse',
                                  action='store_true',
                                  dest='no_input',
                                  default=False,
                                  help="I know what I'm doing, no confirmation please."),
                  )

    def check_unicorns(self):
        p = Popen(['pgrep', '-f', GUNICORN_CMD], stdout=PIPE, stderr=PIPE)
        pids = filter(lambda x: x != '', p.stdout.read().strip().split('\n'))
        if len(pids) > 0:
            print "\nFound running gunicorn processes: \n\t%s" % ', '.join(pids)
        else:
            print "\nNo gunicorns found, you're safe now."

    def supervisor(self, command):
        supervisor_command = 'sudo supervisorctl %s commcare-hq-%s-django' % (command, settings.SERVER_ENVIRONMENT)
        print "\tCalling %s" % supervisor_command
        p = Popen(supervisor_command.split(' '), stdout=PIPE, stderr=PIPE)
        supervisor_results = p.stdout.read()
        print "\tResults: %s" % supervisor_results
        return supervisor_results

    def handle(self, *args, **options):
        aggressive = options['aggressive']

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
                if not aggressive:
                    print "\tShutting down django via supervisor:"
                    self.supervisor("stop")
                print "\tProceeding to kill gunicorn processes."
                self.check_unicorns()
                pk = Popen(['pkill', '-9', '-f', GUNICORN_CMD], stdout=PIPE, stderr=PIPE)
                print pk.stdout.read()

                if not aggressive:
                    print "\tRestarting django via supervisor:"
                    self.supervisor("start")
                AuditEvent.audit_command()
            else:
                print "\tNo slaying...for now"








