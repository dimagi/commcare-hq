Formplayer in HQ
================

This documentation describes how `formplayer <https://github.com/dimagi/formplayer/>`__ fits into the larger
CommCare system, especially how it relates to CommCare HQ development. For details on building, running, and
contributing to formplayer, see the formplayer repository.

What Is Formplayer?
^^^^^^^^^^^^^^^^^^^

Formplayer is a Java Spring Boot server that wraps `commcare-core <https://github.com/dimagi/commcare-core>`_
and presents its main features as an HTTP API. CommCare HQ's Web Apps, App Preview, and SMS Forms features are
built on top of it:

* Web Apps is a single-page application, inlined into a CommCare HQ template, that provides a web UI backed by the formplayer API.
* App Preview is essentially the same as web apps, but embedded as a cell-phone-shaped iframe within the App Builder.
* SMS Forms serializes a form filling session over SMS in a question / answer sequence that is handled by the main HQ process, which hits formplayer's API to send answers and get the next question.

Repository Overview
^^^^^^^^^^^^^^^^^^^

.. image:: images/formplayer_repo_overview.png

* `commcare-android <https://github.com/dimagi/commcare-android>`_: The UI layer of CommCare mobile.
* `commcare-core <https://github.com/dimagi/commcare-core>`_: The CommCare engine, this powers both CommCare mobile and formplayer. Mobile uses the ``master`` branch, while formplayer uses the ``formplayer`` branch. The two branches have a fairly small diff.
* `formplayer <https://github.com/dimagi/formplayer>`__
* `commcare-hq <https://github.com/dimagi/commcare-hq>`_: HQ hosts web apps and the processes that run SMS forms.


Relevant Architectural Decisions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

While a full detailing of formplayer's architecture is beyond the scope of this document, a few architectural
decisions are particularly useful for HQ devs who are new to formplayer to understand.

Sandboxes
+++++++++
Sharing the commcare-core code between mobile and formplayer allows us to keep CommCare Android and web apps
essentially compatible. However, because commcare-core was first written for mobile some of the
paradigms it uses make more sense on mobile than on the web. Mobile is offline-first, so submitting
up newly entered data and syncing back down changes others have made are intentional steps designed not to block
someone who was unable to reach the server for hours, days, or longer. That model makes very
little sense on the always-online Web Apps, but the sync/restore process is still a core part of the working model.
There's even a "Sync" button shown to the user in the web apps UI.

Rather than always fetching the latest data from the source of truth, formplayer works off of locally synced subsets of data
like those that would be on people's phones if every user had their own phone. These "sandboxes" are stored as Sqlite DB files,
as they are on the phone. A phone typically has one db file and one user, whereas on formplayer, there
are as many db files as there are users, i.e. tens of thousands. Each file has its own slice of the data synced
down from the source of truth, but always just a little bit out of date if anyone's updated it after their last
sync.

Request routing
+++++++++++++++
Each user is tied by a ``formplayer_session`` cookie directly to a machine. The cookie is just a routing hint that
contains the user id but doesn't constitute authentication.  That sticky association only changes if we add or
remove machines, and in that case, the minimum number of associations are changed to rebalance it because we use
`"consistent hashing" <http://nginx.org/en/docs/http/ngx_http_upstream_module.html#hash>`_.
In steady state, one user's requests will always be served by the same machine.

An obvious side effect of that is that if a machine is down, all users assigned to that machine will not be able to do anything until the
machine is back up. During a formplayer deploy, when we have to restart all formplayer processes, a rolling
restart doesn't help uptime, since for every individual user their machine's process will be down while it restarts.

Routing implications for adding and removing machines
-----------------------------------------------------

It's expensive to delete a user's sqlite sandbox, because rebuilding it requires requesting a full restore from
HQ, but it's always **safe** to delete it, because that rebuild from the source of truth will get the user back to
normal. This property makes removing machines a safe operation.
Similarly, adding new machines doesn't pose an issue because the subset of users
that get routed to them will just have their sqlite db file rebuilt on that machine the next time it's needed.
These sandbox db files effectively serve as a cache.

What **does** cause a problem is if a user is associated with machine A, and then gets switched over to machine
B, and then goes back to machine A. In that situation, any work done on machine A wouldn't get synced to machine B
until the next time the user did a "sync" on machine B. Until then, they would be working from stale data. This is
especially a problem for SMS Forms, where the user doesn't have an option to explicitly sync, and where if the
underlying case database switches mid-form or between consecutive forms to a stale one, the user will see very
unintuitive behavior. Formplayer currently doesn't have a concept of "this user has made a request handled by a
different formplayer machine since the last time this machine saw this user"; if it did and it forced a sync in
that situation, that would mostly solve this problem. This problem can show up if you expand the cluster and then
immediately scale it back down by removing the new machines.

Lastly, sqlite db files don't hang around forever. So that stale files don't take up ever more disk, all formplayer
sqlite db files not modified in the last 5 days are regularly deleted. The "5 days" constant is set by
`formplayer_purge_time_spec <https://github.com/dimagi/commcare-cloud/blob/e5871a3dca4c444beb55855a7ba6b8f4e3473c8f/environments/production/public.yml#L61>`_.

Balancing issues for large numbers of machines
----------------------------------------------

Each user has a widely variable amount of traffic, and the more machines there are in the system, the wider the spread
becomes between the least-traffic machine and the most-traffic machine, both statistically and in practice.

If you randomly select 10,000 values from `[1, 10, 100, 100]` and then divide them into `n` chunks,
the sum of the values in each chunk have a wider distribution the
larger `n` is. Here the values represent each user and how much traffic they generate, so this is meant to show
that the more machines you have for a fixed number of users using this rigid load balancing method, the wider the
spread is between the least-used and most-used machine.

This means that fewer, larger machines is better than more smaller machines. However, we have also found
that formplayer performance drops sharply when you go from running on
machines with 64G RAM and 30G java heap to machines with 128G RAM and (still) 30G java heap. So for the time being
our understanding is that the max machine size is 64G RAM to run formplayer on. This, of course, limits our ability
to mitigate the many-machines load imbalance problem.

Navigation
^^^^^^^^^^

The purpose of this section is to introduce formplayer navigation *in the context of CommCare HQ*. CommCare allows
for a wide variety of behavior, but applications built in HQ use a subset of this behavior and a few common
workflows.

For a full picture of CommCare, see the `commcare-core wiki <https://github.com/dimagi/commcare-core/wiki/>`_, in
particular

* `CommCare Session <https://github.com/dimagi/commcare-core/wiki/SessionStack>`_
* `CommCare Session External Instance Definition <https://github.com/dimagi/commcare-core/wiki/commcaresession>`_
* `CommCare 2.0 Suite Definition <https://github.com/dimagi/commcare-core/wiki/Suite20>`_

Note: This document uses case-centric language, because that is the entity most often used in HQ. Any references to
cases could be changed to any model that is backed by a similar XML structure.

The CommCare Session
++++++++++++++++++++

A single CommCare session is (loosely) defined as the series of **actions** taken by a user from the time that they
view the home screen until the time that they press "Submit" in a form, plus the **data**
that is collected and persisted along the way as those those actions are taken.

The end goal of a session is to complete a form. This implies:

* Every CommCare form has specific pieces of data that it needs to have access to in order to function properly.

* Forms always get that data by referencing the session, i.e. ``instance('commcaresession')/session/data/blahblahblah``

* The flow of a CommCare session is always structured to ensure that a user has "collected" all of the data that a certain form needs before allowing the user to enter that form.

The session is implemented by the class `CommCareSession <https://github.com/dimagi/commcare-core/blob/master/src/main/java/org/commcare/session/CommCareSession.java>`_,
with its data stored in ``CommCareSession.collectedDatums``. The session also keeps track of the current menu or form id, in ``CommCaseSession.currentCmd``.
`CommCareSession.getNeededData <https://github.com/dimagi/commcare-core/blob/d791a58880cfe22e4d23b7deaef12a0cb1e4aeee/src/main/java/org/commcare/session/CommCareSession.java#L193-L217>`_
determines what information is needed next, based on the current command on the data needed by entries associated
with that command, and ``MenuSessionRunnerService`` (see below) uses that need to determine what screen to show.

Each piece of **data** in the session is either:

* "Action history" - information about the actions that a user has taken in the session so far. This is useful to implement "back" navigation, and it is also a necessary part of formplayer being a RESTful service (see the section below on replaying sessions).

* "Collected data" - pieces of raw app data that will be used later within some form in the app, like case ids

The **actions** a user can take in the session are:

* Select a menu - this adds a "command id", which identifies the menu, to the session

* Select a case (or confirm selection of a case) - this adds a "datum" to the session, the case's id, which both serves as a record of the selection action and identifies the case.

* Select a form - this adds a "command id", which identifies the form, to the session

Screens
+++++++

This section answers the question, "After each user action in a CommCare app, how does CommCare decide what screen to show next?"

There are three principles used to answer this question:

1. Order matters: CommCare will never instruct the user to collect a datum that is listed later in a <session> block before one listed earlier in that same block. This allows ``<datum>s`` that come later in the list to refer to ones that came earlier, which is useful in workflows such as selecting a case that must be the child of a previously selected case.

1. Equality of datums: CommCare is at all times aware of a universe of all datums which are required by at least one form in the app - some of which may overlap. The most notable effect of this is that if all of the possible actions a user is considering all require the same datum, CommCare will ask the user to select that datum before moving on to select the action.

1. Never collect unnecessary data

At any given time, there is one piece of data that the app is focused on acquiring, and the screen that CommCare shows is determined by the 'type' of that piece of data:

* If CommCare is looking for a "datum", it will show a case list

* If CommCare is looking for a "command id", it will show a menu screen

Before the "Start" button is pressed, CommCare is always looking for a command id (module or form), which is why the app's root module menu is always the first screen to be shown.

``commcare-core``, the engine shared by CommCare mobile, the CommCare CLI, and formplayer, has the following types of screens:

* ``MenuScreen`` - Displays a list of menus and/or forms.

* ``EntityScreen`` - Displays a case list.

* ``QueryScreen`` - Used for case search and claim, see section below. This is the screen the displays search fields. Search results are displayed using an ``EntityScreen``.

* ``SyncScreen`` - Used for case search and claim, see section below. This screen isn't visible to the user, but it controls the sending of the claim request and then syncing.

``formplayer`` uses these same screens, but ``FormplayerQueryScreen`` and ``FormplayerSyncScreen`` extend
``QueryScreen`` and ``SyncScreen``. This means that formplayer and the CLI use different logic for case search &
claim.

A screen's job is to handle input, which often includes updating the session - either setting the ``currentCmd`` or
adding an item to `collectedDatums``.

The ``EntityScreen`` is a special case, since it handles what, from the user's perspective, are two screens: the
case list and the case detail confirmation. ``EntityScreen`` acts as a "host" screen, extending
``CompoundScreenHost``. The ``EntityDetailSubscreen``, which handles the case detail, is not a full ``Screen`` but
rather a ``Subscreen`` that updates its host, the entity screen, which is then in charge of updating the session.

Case lists that allow for the selection of multiple entities have further special handling, described in
`formplayer docs <https://github.com/dimagi/formplayer/wiki/Multi-Select-Case-Lists>`_.

Selections
++++++++++
User activity in CommCare is oriented around navigating to and then submitting forms. User actions are represented
as a series of "selections" that begin at the app's initial list of menus and eventually end in form entry.

The selections list keeps track of actions the user has taken in the current session. Every time a user takes a
navigation action (selecting a menu, case, or form), web apps updates the ``selections`` list and sends it to
formplayer as part of a ``navigate_menu`` request.

A single selection can be:

* An integer index. This is used for lists of menus and/or forms and represents the position of the selected item.
* A case id. This indicates that the user selected the given case.
* The keyword ``action`` and an integer index, such as ``action 0``. This represents the user selecting an action on a detail screen. The index represents the position of the action in the detail's list of actions.

Replaying sessions
------------------

For an example, consider the selections ``[1, 'abc123', 0]``. These indicate that a user selected the second visible menu, then selected case
``abc123``, then selected the first visible menu (or form). This might have mapped to the following requests:

* ``navigate_menu_start`` to view the first screen, a list of menus
* ``navigate_menu`` with selections ``[1]`` to select the first menu, which leads to a case list
* ``get_details`` with selections ``[1]`` to select a case and show its details
* ``navigate_menu`` with selections ``[1, 'abc123']`` to confirm the case selection, which leads to a list of forms
* ``navigate_menu`` with selections ``[1, 'abc123', 0]`` to select the first form
* ``submit-all`` to submit the form when complete, which sends the user back to the first list of menus

Because formplayer is a RESTful service, each of these individual request plays through all of the given
selections, even those that were already completed earlier. If an early selection contained an expensive operation,
that operation can slow down requests for the rest of the session. Selections that cause side effects will cause
them repeatedly.

`MenuSessionRunnerService <https://github.com/dimagi/formplayer/blob/master/src/main/java/org/commcare/formplayer/services/MenuSessionRunnerService.java>`_
controls formplayer navigation. This largely happens in ``advanceSessionWithSelections``, which loops over the
selections list, replaying the full session as described above.

On each iteration, ``advanceSessionWithSelections`` determines the current screen based on the state of the
``MenuSession`` and then adds the next selection. It handles special navigation, which mostly relates to case
search and claim (see below). When it runs out of selections, it returns the current menu, which is a response
bean.

Case Search and Claim
+++++++++++++++++++++
Case search and claim allows a user to gain access to a case not already in their casedb. Case search and claim are
implemented using a "remote request", which is an extension of an entry. While an entry's purpose is to get the
user into an XForm, a remote request's purpose is to send a request to the server (HQ).

From the case list, the user takes a case search action. This presents them with a multi-field search screen, the
``QueryScreen``. Their search inputs are sent as a request to HQ, which queries ElasticSearch for all cases in the
domain and sends an XML document back with the results. Formplayer displays these results as a case list, an
``EntityScreen``. When the user selects and then confirms a case, formplayer sends a POST request to HQ. This
request, configured as part of the app, creates an extension case for the selected case. When this request returns,
formplayer syncs, causing the selected case to be added to the user's casedb. CommCare then "rewinds" to the
case list where the user started, selecting the case they claimed and moving them on to the next form or menu,
using a mark/rewind mechanism discussed
`elsewhere <https://github.com/dimagi/commcare-core/wiki/SessionStack#mark-and-rewind>`_.

CommCare treats case search and claim as pieces of data to be gathered. Just as CommCare
typically is expecting either a command (a menu or form) or a datum (a case), it can instead expect a
``QUERY_REQUEST`` or a ``SYNC_REQUEST``, which indicate it should display a ``QueryScreen`` or handle a
``SyncScreen`` (send the post request and subsequent sync).

Alternate Case Search Workflows
-------------------------------
For projects using CommCare mobile, case search and claim is typically an unusual workflow. However, projects that
use web apps, and therefore have guaranteed connectivity, may use it much more heavily, even to the point that the user
is unaware of their casedb and always uses case search to find cases.

To support this approach, HQ allows apps to be configured with several alternate navigation flows. These workflows
are gated by the ``USH_CASE_CLAIM_UPDATES`` feature flag.

The default case search and claim workflow shows the user the following screens:

* A menu screen, where the user selects a form/menu that requires a case

* A case list screen displaying the user's casedb, where the user elects to go into case search

* A case search screen, with search inputs for various fields

* A case list screen displaying the results of the search

The alternate case search workflows allow the user to skip  the casedb case list, the case search screen, or both.

To handle this skipping behavior, every iteration over the selections list in
``MenuSessionRunnerService.advanceSessionWithSelections`` checks to see if there are any "automatic" actions
needed, in ``autoAdvanceSession``.
