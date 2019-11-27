import datetime
from django.core.management import BaseCommand

from django_prbac.models import Role


class Command(BaseCommand):

    def handle(self, **kwargs):
        new_plans = [
            'community_plan_v2',
            'standard_plan_v1',
            'pro_plan_v1',
        ]
        for plan_slug in new_plans:
            role = Role.objects.filter(slug=plan_slug).first()
            if role:
                print('deprecating role {}'.format(plan_slug))
                now_slug = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
                role.slug = "{}_{}".format(plan_slug, now_slug)
                role.save()
            else:
                print('no role for deprecation {}'.format(plan_slug))
