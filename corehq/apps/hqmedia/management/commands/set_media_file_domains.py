from optparse import make_option
from django.core.management.base import BaseCommand
from corehq.apps.domain.models import Domain

DOMS_TO_IGNORE = ['bug-reports']  # we don't care about updating media to include this domain
class Command(BaseCommand):
    help = 'Adds domains that have apps w/ media to that media files list of valid domains'

    option_list = BaseCommand.option_list + (
        make_option('-s', '--since',
            help="Begin at this domain. (Alphabetically Descending"),
        make_option('-d', '--domain',
            help="Check only this domain"),
        )

    def handle(self, *args, **options):
        if options.get('domain'):
            domains = [Domain.get_by_name(options.get('domain'))]
        else:
            domains = Domain.get_all()

        since = options.get('since')
        seen_since = False
        for d in domains:
            if since and not seen_since:
                if d.name == since:
                    seen_since = True
                else:
                    continue

            if d.name in DOMS_TO_IGNORE:
                continue
            try:
                for app in d.full_applications():
                    try:
                        if app.is_remote_app():
                            continue
                        for _, m in app.get_media_objects():
                            if app.domain not in m.valid_domains:
                                m.valid_domains.append(app.domain)
                                self.stdout.write("adding domain %s to media file %s" % (app.domain, m._id))
                                m.save()
                    except Exception as e:
                        self.stdout.write("Error in app %s-%s: %s" % (app.domain, app._id, e))
            except Exception as e:
                self.stdout.write("Error in domain %s: %s" % (d.name, e))
