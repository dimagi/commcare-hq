from couchdbkit.ext.django.testrunner import CouchDbKitTestSuiteRunner
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models.loading import get_app
import settingshelper

class HqTestSuiteRunner(CouchDbKitTestSuiteRunner):
    """
    A test suite runner for Hq.  On top of the couchdb testrunner, also
    apply all our monkeypatches to the settings.
    
    To use this, change the settings.py file to read:
    
    TEST_RUNNER = 'Hq.testrunner.HqTestSuiteRunner'
    """
    
    dbs = []
    def setup_test_environment(self, **kwargs):
        # monkey patch TEST_APPS into INSTALLED_APPS so that tests are run for them
        # without having to explicitly have them in INSTALLED_APPS
        # weird list/tuple type issues, so force everything to tuples
        settings.INSTALLED_APPS = tuple(settings.INSTALLED_APPS) + tuple(settings.TEST_APPS)
        return super(HqTestSuiteRunner, self).setup_test_environment(**kwargs)
        
    def setup_databases(self, **kwargs):
        self.newdbname = self.get_test_db_name(settings.COUCH_DATABASE_NAME)
        print "overridding the couch settings!"
        new_db_settings = settingshelper.get_dynamic_db_settings(settings.COUCH_SERVER_ROOT, 
                                                                 settings.COUCH_USERNAME, 
                                                                 settings.COUCH_PASSWORD, 
                                                                 self.newdbname, 
                                                                 settings.INSTALLED_APPS)
        settings.COUCH_DATABASE_NAME = self.newdbname
        for (setting, value) in new_db_settings.items():
            setattr(settings, setting, value)
            print "set %s settting to %s" % (setting, value)

        return super(HqTestSuiteRunner, self).setup_databases(**kwargs)

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        if not test_labels:
            test_labels = [self._strip(app) for app in settings.INSTALLED_APPS
                           if not app in settings.APPS_TO_EXCLUDE_FROM_TESTS
                           and not app.startswith('django.')]

        for l in test_labels:
            try:
                get_app(l)
            except ImproperlyConfigured:
                print l
        return super(HqTestSuiteRunner, self).run_tests(test_labels, extra_tests, **kwargs)

    def _strip(self, app_name):
        return app_name.split('.')[-1]