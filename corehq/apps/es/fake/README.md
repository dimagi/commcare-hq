# Writing tests by using ES fakes

In order to be able to use these ES fakes. All calls to ES in the code you want to test
must go through one of the ESQuery subclasses, such as UserES or GroupES.

In testing, a **fake** is a component that provides an actual implementation of an API,
but which is incomplete or otherwise unsuitable for production.
(See http://stackoverflow.com/a/346440/240553 for the difference between fakes, mocks, and stubs.)

`ESQueryFake` and its subclasses (`UserESFake`, etc.) do just this for the `ESQuery`
classes. Whereas the real classes hand off the work to an Elasticsearch cluster,
the fakes do the filtering, sorting, and slicing in python memory, which is lightweight
and adequate for tests. Beware that this method is, of course,
inadequate for assuring that the `ESQuery` classes themselves are producing
the correct Elasticsearch queries, and also introduces the potential for bugs to go
unnoticed because of bugs in `ESQueryFake` classes themselves. But assuming correct
implementations of the fakes, it does an good job of testing the calling code,
which is usually the primary subject of a test.

The anatomy of a fake is something like this:
- For each real `ESQuery` subclass (I'll use `UserES` as the example),
  there is a corresponding fake (`UserESFake`).
  In cases where such a fake does not exist when you need it,
  follow the instructions below for getting started on a new fake.
- For each filter method or public method used on the `ESQuery` base class
  a method should exist on `ESQueryFake` that has the same behavior
- For each filter method on `UserES`, a method should exist on `UserESFake`
  that has the same behavior.

New fakes and methods are implemented only as actually needed by tests
(otherwise it's very difficult to be confident the implementations are correct),
so until some mythical future day in which all code that relies on ES goes through
an `ESQuery` subclass and is thoroughly tested, the fake implementations are
intentionally incomplete. As such, an important part of their design is that they alert
their caller (the person using them to write a test) if the code being tested calls a
method on the fake that is not yet implemented. Since more often than not a number of
methods will need to be added for the same test, the fakes currently are designed to have
each call to an unimplemented filter result in a no-op, and will output a logging statement
telling the caller how to add the missing method. This lets the caller run the test once
to see a print out of every missing function, which they can then add in one go and re-run
the tests. (The danger is that they will miss the logging output; however in cases where
a filter method is missing, it is pretty likely that the test will fail which will prod
them to look further and find the logging statement.)

## How to set up your test to use ES fakes

Patch your test to use `UserESFake` (assuming you want to patch `UserES`),
making sure to patch `UserES` in the *files in which it is used*, not the file in which
it is declared

```diff
+ @mock.patch('corehq.apps.users.analytics.UserES', UserESFake)
+ @mock.patch('corehq.apps.userreports.reports.filters.choice_providers.UserES', UserESFake)
  class MyTest(SimpleTestCase):
      def setUp(self):
...
+         UserESFake.save_doc(user._doc)
...
      def tearDown(self):
          UserESFake.reset_docs()
```

## How to set up a new ES fake

Adding a new fake is very easy. See [users_fake.py](./users_fake.py) for a simple example.
