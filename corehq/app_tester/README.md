App Tester
==========

The App Tester allows app builders to create simple tests for their forms. These tests are written in the YAML
document format, chosen for its legibility, and because app builders need nothing more than a simple text editor
to create tests. See below for an example.

The App Tester can be used from CommCareHQ, or remotely as a management command.

Sample Test
-----------

    # App Tester Example
    ---
    login:
      host: http://www.commcare.org/
      domain: example
      username: john.smith
      password: s3cr3t
      app: Case Management

    tests:
      - Mobile worker should be able to register a case:
          result: success
          modules:
            - Registration:
                forms:
                  - Registration:
                      answers:
                        - welcome_message:
                        - name: Joe Bloggs
                        - sample_choice_question: choice1
                        - sample_number_question: 1
      - An invalid choice should fail:
          result: error
          errorMessage: Invalid choice
          modules:
            - Registration:
                forms:
                  - Registration:
                      answers:
                        - welcome_message:
                        - name: Joe Bloggs
                        - sample_choice_question: choice1
                        - sample_number_question: 1
            - Follow Up:
                case: Joe Bloggs
                forms:
                  - Visit:
                      answers:
                        - welcome_message:
                        - sample_choice_question: not_a_valid_choice
                        - sample_number_question: Sixty hundred eleventy and point six


Login details
-------------

In order for the App Tester to log in, you will need to give it the details of the server and the mobile worker to
log in as.


Tests
-----

Give each test a name that describes the expected behaviour it is testing, like "Mobile worker should be able to
register a case".


Assertions
----------

Each test asserts a result. Possible values are:

* success: The test submits all forms successfully
* failure: The test fails to submit all forms
* error: More specific than just "failure". An error occurs. Add another key:
    * errorMessage: Set this to part, or all, of the error message
* assertCaseProperty: More specific that "success". Add the following keys:
    * caseType: The case type
    * caseName: The name of the case
    * casePropertyEquals: Its expected value
  In the future property comparisons beyond "Equals", like "GreaterThan" and "IsNotSet", can be added as they are
  needed or requested.


A Little Testing Philosophy for FMs
-----------------------------------

Bear in mind that, as with science, you are more interested in counter-examples than examples. In other words, you
certainly want to show that your app *can* work, but it is more important to test where it might break.


NOTES TO NOAH
=============

I started with this document, to sort out in my head how I imagined this would be used.

Then I took a top-down approach. I find that keeps the interface as clean as possible. I wrote the management
command, and sample YAML files. The long one is how I'd like it to work in the future, and the MVP was how I would
have liked it to work today. -- No cases, just one form.

Then I wrote utils.py. That stuff should probably move out, but I figured it would be obvious where it should go
as I progressed -- and now it seems obvious that it needs to be renamed "test_runner.py", or something like that.

Then I got to the hard part -- the client and session classes (client.py). Giovanni's SMS code wraps quite a bit of
touchforms and formplayer stuff in a nice way, and I figured I'd follow his example, but simplify where I could.
Iterating questions could be done much simpler, I think. And session management need not be as complicated for us
because we're just a test runner, and don't need persistence.

So, basically, my next steps would be to write FormPlayerApiClient, FormSession, and the end of utils.run_test

Not trivial -- but there is a lot of potential for the fun stuff -- cleaning and simplifying -- imho.

And then deleting "NOTES TO NOAH".
