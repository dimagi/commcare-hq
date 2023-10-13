from nose.tools import nottest

from corehq.apps.object_testing.framework.context_factory import ContextFactor
from corehq.apps.object_testing.framework.runner import TestRunnerFactory


@nottest
def execute_object_test(object_test):
    factory = ContextFactor.get_factory(object_test.context_factory)
    context = factory.get_context(object_test.input)
    expected = factory.get_context(object_test.expected)

    runner = TestRunnerFactory.get_runner(object_test.content_object)
    return runner(object_test.content_object, context, expected).run()
