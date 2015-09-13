from django.db import models

from .exceptions import DeployAlreadyInProgress
from .utils import get_machines, trigger_chief_deploy


class Deploy(models.Model):
    """
    A Deploy represents a single deploy from Chief
    """
    in_progress = models.BooleanField(default=False, db_index=True)
    success = models.BooleanField(default=False, db_index=True)
    complete = models.BooleanField(default=False, db_index=True)
    log_file = models.TextField()
    date_created = models.DateTimeField(auto_now_add=True)
    env = models.CharField(max_length=255)

    @classmethod
    def current_deploy(cls, env):
        try:
            return Deploy.objects.get(in_progress=True, env=env)
        except Deploy.MultipleObjectsReturned:
            raise DeployAlreadyInProgress
        except Exception:
            return None

    @classmethod
    def current_deploys(cls):
        from .views import ENVIRONMENTS
        deploys = []
        for env in ENVIRONMENTS:
            deploys.append(Deploy.current_deploy(env))
        return filter(None, deploys)

    def deploy(self):
        deploys_in_progress = Deploy.objects.filter(
            in_progress=True, env=self.env
        ).count()

        if deploys_in_progress:
            raise DeployAlreadyInProgress

        self.in_progress = True
        self.save()
        #trigger_chief_deploy()

    def as_json(self):
        return {
            'in_progress': self.in_progress,
            'success': self.success,
            'date_created': self.date_created,
            'env': self.env,
            'machines': [m.as_json() for m in self.machine_set.all()],
            'stages': [s.as_json() for s in self.stage_set.all()],
        }
