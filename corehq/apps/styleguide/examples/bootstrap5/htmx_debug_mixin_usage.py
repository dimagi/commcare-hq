from corehq.apps.hqwebapp.views import BasePageView
from corehq.util.htmx_action import HqHtmxActionMixin
from corehq.util.htmx_debug import HqHtmxDebugMixin


class TodoListDemoView(HqHtmxDebugMixin, HqHtmxActionMixin, BasePageView):
    simulate_slow_response = True
    slow_response_time = 3
    simulate_flaky_gateway = False
    ...  # The rest of the view implementation would go here
