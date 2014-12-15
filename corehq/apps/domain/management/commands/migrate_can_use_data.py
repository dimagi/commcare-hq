from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import LabelCommand
from corehq.apps.domain.models import Domain


class Command(LabelCommand):
    help = "Migrates the 'can_use_data' field to not be the opposite of what it sounds like."
    args = ""
    label = ""

    def handle(self, *args, **options):
        opted_out_domains = []
        failed = []
        for domain in Domain.get_all():
            try:
                domain.internal.can_use_data = not domain.internal.can_use_data
                domain.save()
                if not domain.internal.can_use_data:
                    opted_out_domains.append(domain.name)
            except Exception:
                failed.append(domain.name)


        message = 'The following domains have opted out of data use:\n{domains}'.format(
            domains='\n'.join(opted_out_domains)
        )
        print message
        if settings.EULA_CHANGE_EMAIL:
            send_mail('Data use flags flipped', message, settings.DEFAULT_FROM_EMAIL,
                      [settings.EULA_CHANGE_EMAIL])
