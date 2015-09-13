from django.test import TestCase

from ..models import Deploy
from ..exceptions import DeployAlreadyInProgress


class DeployModelTest(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.env = 'test'

    def test_create_deploy_model(self):
        deploy = Deploy.objects.create(env=self.env)

        self.assertEqual(deploy.success, False)
        self.assertEqual(deploy.in_progress, False)
        self.assertEqual(deploy.env, self.env)

        deploy.deploy()
        self.assertEqual(deploy.in_progress, True)
        self.assertEqual(deploy.success, False)

    def test_deploy_when_deploy_is_in_progress(self):
        deploy = Deploy.objects.create(env=self.env)
        deploy.deploy()

        deploy2 = Deploy.objects.create(env=self.env)
        with self.assertRaises(DeployAlreadyInProgress):
            deploy2.deploy()
