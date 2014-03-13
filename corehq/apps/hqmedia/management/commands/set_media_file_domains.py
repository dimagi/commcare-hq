from django.core.management.base import BaseCommand
from corehq import Domain


class Command(BaseCommand):
    help = 'Adds domains that have apps w/ media to that media files list of valid domains'

    def handle(self, *args, **options):
        for d in Domain.get_all():
            for app in d.full_applications():
                if app.is_remote_app():
                    continue
                for _, m in app.get_media_objects():
                    if app.domain not in m.valid_domains:
                        m.valid_domains.append(app.domain)
                        self.stdout.write("adding domain %s to media file %s" % (app.domain, m._id))
                        m.save()
