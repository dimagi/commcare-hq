from nose.tools import nottest

from corehq.apps.object_testing.framework.context_factory import ContextFactor
from corehq.apps.object_testing.framework.runner import TestRunnerFactory


@nottest
def execute_object_test(object_test):
    factory_slug = object_test.context_factory
    factory = ContextFactor.get_factory(factory_slug, object_test.input)
    context = factory.get_context()

    runner = TestRunnerFactory.get_runner(object_test.content_object)
    return runner(object_test.content_object, context, object_test.expected).run()
