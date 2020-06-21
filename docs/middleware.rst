==========
Middleware
==========

What is middleware?
===================

HQ uses a number of types of middleware, defined in ``settings.py``.
For background on middleware, see the `Django docs <https://docs.djangoproject.com/en/3.0/topics/http/middleware/>`_

TimeoutMiddleware
=================

``TimeoutMiddleware`` controls a session-based inactivity timeout, where the user is logged out after a period of inactivity.

The default timeout, defined in ``settings.py`` as ``INACTIVITY_TIMEOUT``, is two weeks, long enough that regular
users will not encounter it.

Most of ``TimeoutMiddleware`` deals with domains that enforce a shorter timeout for security purposes.

The shorter timeout is enabled using the "Shorten Inactivity Timeout" checkbox in Project Settings > Privacy, and
stored as the ``Domain`` attribute ``secure_sessions``. This document wil refer to domains using this feature as "secure" domains.
By default, secure domains time their users out after 30 minutes of inactivity. This duration is controlled by
``SECURE_TIMEOUT`` in ``settings.py``.

"Activity" refers to web requests to HQ. This includes formplayer requests, as formplayer issues a request to HQ
for session details that extends the user's session; see ``SessionDetailsView``. In secure domains,
there is also javascript-based logic in ``hqwebapp/js/inactivity`` that periodically pings HQ for the purpose of
extending the session, provided that the user has recently pressed a key or clicked their mouse.

When a user's session times out, they are logged out, so their next request will redirect them to the login page.
This works acceptably for most of HQ but is a bad experience when in an area that relies heavily on ajax requests, which
will all start to fail without indicating to the user why. To avoid this there is a logout UI, also
controlled by ``hqwebapp/js/inactivity``, which tracks when the user's session is scheduled to expire. This UI pops
up a warning dialog when the session is close to expiring. When the session does expire, the UI pops up a dialog
that allows the user to re-login without leaving the page. This UI is enabled whenever the user is on a
domain-specific page and has a secure session. Note that the user's session may be secure even if the domain they
are viewing is not secure; more on this below.

A user's session is marked secure is any of the following are true:

* The user is viewing a secure domain.
* The user is a member of **any** domain that uses secure sessions.
* The session has already been marked secure by a previous request.

This behavior makes secure sessions "sticky", following the user around after they visit a secure domain. Note that
the session is cleared when the user logs out.

The feature flag ``SECURE_SESSION_TIMEOUT`` allows domains to customize the length of their timeout. When this is
on, the domain can specify a number of minutes, which will be used in place of the default 30-minute
``SECURE_TIMEOUT``. When a user is affected by multiple domains, with different timeout durations, the minimum
duration is used. As with the secure session flag itself, the relevant durations are the current domain, and other
domains where the user is a member, and the duration value currently stored in the session. So a user who belongs
to 2 secure domains, one with the standard 3-minute timeout and one with a 15-minute timeout, will always
experience a 15-minute timeout. A user who belogns to no secure domains but who visits a domain with a 45-minute
timeout will then experience a 45-minute timeout until the next time they log out and back in.
