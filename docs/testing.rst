=======
Testing best practices
=======

Test set up
===========

Doing a lot of work in the ``setUp`` call of a test class means that it will be run on every test. This
quickly adds a lot of run time to the tests. Some things that can be easily moved to ``setUpClass`` are domain
creation, user creation, or any other static models needed for the test.

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
the same set up, you can write a setup method for the entire package or module. More information on that can be found `here <http://pythontesting.net/framework/nose/nose-fixture-reference/#package>`_.

Test tear down
==================

It is important to ensure that all objects you have created in the test database are deleted when the test
class finishes running. This often happens in the ``tearDown`` method or the ``tearDownClass`` method.
However, unneccessary cleanup "just to be safe" can add a large amount of time onto your tests.


Using SimpleTestCase
====================

The SimpleTestCase runs tests without a database. Many times this can be achieved through the use of the `mock
library <http://www.voidspace.org.uk/python/mock/>`_. A good rule of thumb is to have 80% of your tests be unit
tests that utilize ``SimpleTestCase``, and then 20% of your tests be integration tests that utilize the
database and ``TestCase``.

CommCareHQ also has some custom in mocking tools.

- `Fake Couch <https://github.com/dimagi/fakecouch>`_ - Fake implementation of CouchDBKit api for testing purposes.
- `ESQueryFake <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/es/fake/es_query_fake.py>`_ - For faking ES queries.


Squashing Migrations
====================

There is overhead to running many migrations at once. Django allows you to squash migrations which will help
speed up the migrations when running tests.
