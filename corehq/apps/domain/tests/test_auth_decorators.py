from django.test import SimpleTestCase


CHECK_FAILED = 'check failed'


def challenge(check):
    def decorator(view):
        def wrapper(request, *args, **kwargs):
            auth = check(request)
            if auth:
                return view(request, *args, **kwargs)

            return CHECK_FAILED
        return wrapper
    return decorator


passing_decorator = challenge(lambda request: True)
failing_decorator = challenge(lambda request: False)


class LoginOrChallengeTest(SimpleTestCase):

    def test_challenge(self):
        request = object()

        @passing_decorator
        def test(request, *args, **kwargs):
            return 'it worked!'

        self.assertEqual('it worked!', test(request))

        @failing_decorator
        def test(request, *args, **kwargs):
            return 'it worked!'

        self.assertEqual(CHECK_FAILED, test(request))
