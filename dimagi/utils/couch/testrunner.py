import sys
from django.conf import settings
from couchdbkit.ext.django import loading as loading
from couchdbkit.ext.django.testrunner import CouchDbKitTestSuiteRunner
from couchdbkit.resource import ResourceNotFound
import settingshelper

class DimagiCouchTestSuiteRunner(CouchDbKitTestSuiteRunner):
    """
    A test suite runner for couchdbkit.  This offers the exact same functionality
    as the default django test suite runner, except that it connects all the couchdbkit
    django-extended models to a test database.  The test database is deleted at the
    end of the tests.  To use this, just add this file to your project and the following 
    line to your settings.py file:
    
    TEST_RUNNER = 'myproject.testrunner.DimagiCouchTestSuiteRunner'
    """
    dbs = []

    def setup_databases(self, **kwargs):
        returnval = super(DimagiCouchTestSuiteRunner, self).setup_databases(**kwargs)
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
        # hack - set the other values too
        return returnval


try:
    import xmlrunner
    from django.test.simple import *
    class DimagiCouchXMLTestSuiteRunner(DimagiCouchTestSuiteRunner):
        """XML Runner for running this in a build server with pretty xml report output
        """
        def run_tests(self, test_labels, verbosity=1, interactive=True, extra_tests=[]):
            """
            adapted from xmlrunner.extra.djangotestrunner.run_tests
            """
            self.setup_test_environment()

            settings.DEBUG = False

            verbose = getattr(settings, 'TEST_OUTPUT_VERBOSE', False)
            descriptions = getattr(settings, 'TEST_OUTPUT_DESCRIPTIONS', False)
            output = getattr(settings, 'TEST_OUTPUT_DIR', '.')

            suite = self.build_suite(test_labels, extra_tests) #unittest.TestSuite()
            old_config=self.setup_databases()
            result = xmlrunner.XMLTestRunner(verbose=verbose, descriptions=descriptions, output=output).run(suite)

            self.teardown_databases(old_config)
            self.teardown_test_environment()
            return len(result.failures) + len(result.errors)
            #return self.suite_result(suite, result)


except:
    pass
