======================
Testing infrastructure
======================

Tests are run with `pytest <https://docs.pytest.org/en/stable/>`_.

Pytest plugins
==============

Pytest plugins are used for various purposes, some of which are optional and can
be enabled with command line parameters or environment variables. Others are
required by the test environment and are always enabled.

One very important always-enabled plugin applies
`patches <https://github.com/dimagi/commcare-hq/blob/master/corehq/tests/pytest_plugins/patches.py>`_
before tests are run. The patches remain in effect for the duration of the test
run unless utilities are provided to temporarily disable them. For example,
`sync_users_to_es <https://github.com/dimagi/commcare-hq/blob/master/corehq/util/es/testing.py>`_
is a decorator/context manager that enables syncing of users to ElasticSearch
when a user is saved. Since this syncing involves custom test setup not done by
most tests it is disabled by default, but it can be temporarily enabled using
``sync_users_to_es`` in tests that need it.


======================
Testing best practices
======================

Test set up
===========

The ``setUp`` method is run before each test, so doing a lot of work there can add a lot of run time to the tests.
If possible, consider moving common setup of things that are not mutated by tests into ``setUpClass``. Some things
that can be easily moved to ``setUpClass`` are domain creation, user creation, or any other static models needed
for the test.

Sometimes classes share the same base class and inherit the ``setUpClass`` function. Below is an example:

.. code:: python

    # BAD EXAMPLE

    class MyBaseTestClass(TestCase):

        @classmethod
        def setUpClass(cls):
            ...


    class MyTestClass(MyBaseTestClass):

        def test1(self):
            ...

    class MyTestClassTwo(MyBaseTestClass):

        def test2(self):
            ...


In the above example the ``setUpClass`` is run twice, once for ``MyTestClass`` and once for ``MyTestClassTwo``. If ``setUpClass`` has expensive operations, then it's best for all the tests to be combined under one test class.

.. code:: python

    # GOOD EXAMPLE

    class MyBigTestClass(TestCase):

        @classmethod
        def setUpClass(cls):
            ...

        def test1(self):
            ...

        def test2(self):
            ...

However this can lead to giant Test classes. If you find that all the tests in a package or module are sharing
the same set up, you can use a 'module' or 'package' `scoped fixture <https://github.com/dimagi/pytest-unmagic#fixture-scope>`_.


Test tear down
==============

It is important to ensure that all objects you have created in databases are deleted when the test class finishes
running. The best practice is to use pytest `fixtures <https://github.com/dimagi/pytest-unmagic>`_ or `addCleanup`
or `addClassCleanup` to call cleanup routines. Cleanup can also be done in the ``tearDown`` method or the
``tearDownClass`` method, although pytest fixtures and `add[Class]Cleanup` are preferred because, unlike
`tearDown[Class]`, they get run if `setUp[Class]` raises an exception.

SQL data in non-shard databases is automatically cleaned up on transaction rollback by test classes that override
`django.test.TestCase` or function tests that use pytest-django's `db` fixture, so it is not necessary to delete
SQL data in most cases. One exception to this is the shard dbs, since most usages of shard databases do not support
transactions.

Also beware that unneccessary cleanup "just to be safe" can add a large amount of time onto your tests and should
be avoided.

Functional database tests
=========================

Function tests may access databases by using pytest-django's ``db`` or ``transactional_db`` fixture. This is
similar to extending ``django.test.TestCase`` or ``django.test.TransactionTestCase`` respectively.

.. code:: python

    from unmagic import use

    @use("db")
    def test_database():
        ...


Using ``SimpleTestCase`` and function tests
===========================================

``SimpleTestCase`` and function tests that do not use the ``db`` or ``transactional_db`` fixture run tests without
a database and are often MUCH faster than database tests. Many times this can be achieved through the use of the
`mock library <https://docs.python.org/3/library/unittest.mock.html>`_. A good rule of thumb is to have 80% of your
tests be unit tests that do not touch the database, and 20% of your tests be integration tests that use the
database.

CommCare HQ also has some custom in mocking tools.

- `Fake Couch <https://github.com/dimagi/fakecouch>`_ - Fake implementation of CouchDBKit api for testing purposes.
- `ESQueryFake <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/es/fake/es_query_fake.py>`_ - For faking ES queries.


Squashing Migrations
====================

There is overhead to running many migrations at once. Django allows you to squash migrations which will help
speed up the migrations when running tests.
