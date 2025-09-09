import random
import time

from django.http import HttpResponse


class HqHtmxDebugMixin:
    """
    Use this mixin alongside `HqHtmxActionMixin` to help simulate server
    issues and slow requests locally (or on staging if you like) during
    the development phase.

    Why a separate tool? Making the browser slow with dev tools throttling
    just delays the request TO the server, rather than testing if the server
    itself is slow.

    e.g.:
        class TodoListDemoView(HqHtmxDebugMixin, HqHtmxActionMixin, BasePageView):
            ...

    Remember: Order matters when using mixins. make sure `HqHtmxDebugMixin` appears first
    to have things work properly!
    """
    # Simulate slow server responses by setting this to True and requests will wait
    # ``slow_response_time`` seconds with each request
    simulate_slow_response = False
    slow_response_time = 5  # in seconds

    # When True, simulate flaky gateway problems locally (to test HTMX retries or other error handling)
    simulate_flaky_gateway = False

    def dispatch(self, request, *args, **kwargs):
        if self.simulate_slow_response:
            time.sleep(self.slow_response_time)

        if self.simulate_flaky_gateway and _is_mostly_false():
            return FakeGatewayTimeoutResponse()

        return super().dispatch(request, *args, **kwargs)


class FakeGatewayTimeoutResponse(HttpResponse):
    status_code = 504


def _is_mostly_false():
    """
    This is a little utility to return mostly False and sometimes True.
    Used to simulate a flaky gateway which usually returns a 200 response
    but sometimes returns a 504.
    """
    return bool(random.choices(
        [0, 1],
        weights=[0.8, 0.2]
    )[0])
