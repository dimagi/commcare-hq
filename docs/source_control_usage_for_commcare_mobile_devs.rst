Source Control Usage (Git) for CommCare Mobile Devs
===================================================

The CommCare Mobile team uses `GitHub <https://github.com/dimagi/>`__
and `Git <http://git-scm.com/>`__ for version control and release
management.

If you're coming from Mercurial, I enjoyed `this brief
primer <http://importantshock.wordpress.com/2008/08/07/git-vs-mercurial/>`__
on the key differences


Background
----------

This guide assumes you're installing via the instructions found
`here <https://bitbucket.org/commcare/commcare-odk/wiki/devsetup>`__

The mobile development workspace is composed of four repositories found
`here <https://github.com/dimagi/>`__. They are

-  `javarosa <https://github.com/dimagi/javarosa>`__ - dependent on
   nothing, largely responsible for form functionality
-  `commcare <https://github.com/dimagi/commcare>`__ - dependent only on
   javarosa, contains CommCare-specific code
-  `opendatakit.collect <https://github.com/dimagi/opendatakit.collect>`__
   - dependent only on javarosa, contains android-specific code
-  `commcare-odk <https://github.com/dimagi/commcare-odk>`__ - dependent
   on all three other libraries, contains android-specific code that's
   part of CommCase

Yes, they are horribly name-spaced for legacy reasons

If you intend to install and work entirely from source (that is, if you
want to edit the core javarosa and commcare codebase) then you will need
to clone and pull all four repositories

If you intend to work only on the ODK codebase, then you will need to
only clone and pull the last two repositories

Place each of these repositories in the same root directory. I put mine
in my Eclipse workspace for convenience. So my structure is: ::

    workspace
        \|\_\_ dimagi
            \|\_\_ javarosa
            \|\_\_ commcare
            \|\_\_ commcare-odk
            \|\_\_ opendatakit.collect

Run ``git clone`` for each repository, e.g.,
``git clone https://github.com/dimagi/commcare.git``

Once this is done, you should be able to open all of the code in
Eclipse.


Branching
---------

To submit any changes, you will need to create a branch to do your work
in.

BEFORE beginning work on a task, create a branch for it:
``git branch my_feature_name``

After this, you can list bookmarks with ``git branch`` (which will star
the bookmark you're currently working on) and switch between branches
using ``git checkout branch_name ``\ Note that you can't leave a branch
with uncommitted changes but must either commit
or \ `stash <http://git-scm.com/book/en/Git-Tools-Stashing>`__ your
changes.

To push a given feature, make sure you're in the correct branch and
follow the steps below.


Committing changes
------------------

This assumes that you've made some changes to the code on your local
machine that you want to push to GitHub. The steps are:

#. ``cd`` into the relevant repository
#. ``git status`` to check which files will be submitted,
   ``git diff`` to see their diffs, and ``git add`` to add files to the
   set of files that will be committed.
#. Any files that you want to commit must be added with ``git add`` (or
   ``git rm`` if you're deleting a file). ``git status`` will show you
   which files will be committed and which are still "unstaged." 
#. Once you're satisfied with the set of files, make sure you're on the
   correct branch and run ``git commit`` to submit.
#. Push to GitHub: ``git push origin my_feature_name`` This will create
   a new branch on GitHub with your changes.


Merging your changes via Pull Request
-------------------------------------

Once you're satisfied with the change set you have (this should be one
cohesive unit: IE one bug fix, one feature, one refactor, etc. - not a
combination) you'll want to create a pull request to have that code
merged into trunk. The process for that is:

#. Navigate to the repository you want to pull request (PR),
   e.g., \ `https://github.com/dimagi/commcare <https://github.com/dimagi/commcare>`__
#. Click the green pull request button on the left, above the list of
   files.
#. Set the comparison branch to your feature branch.
#. Once you do this, you should see a list of commits populated at the
   bottom of the screen. Review this to make sure all are correct. In
   particular, make sure you aren't accidentally merging or closing any
   branches.
#. Click the big green "Create pull request" button.
#. Fill out the text boxes with a brief description of what you're doing
   here
#. Again,click the big green "Create pull request" button.

Now other coders on the team will review your PR and submit comments and
corrections via the GitHub interface. You should receive these as email
notifications. When you do, you can make the changes locally and follow
the same procedure as above to push them to your branch, which will make
them appear in your PR.

Important Note: If you have an outstanding Pull Request that is being
reviewed and want to submit a bug fix or another feature that is
unrelated to your original PR, this should be done in a new branch.


Pulling from Trunk
------------------

You'll also want to pull from the trunk to receive other people's
updates: ``git pull``


Further Reading
---------------

That's about all you need to know to get around with the basics of
GitHub with Dimagi. Other sometimes useful functions include:

**Reset**: allows you to remove a change set when you want to backtrack.

**Stash:** Sometimes you'll want to save some code for later but not
push it to your repo; however, some operations require you to have no
outstanding changes. Instead of committing or discarding your changes,
you can choose to stash your changes, moving them into temporary
storage. Later, you can move them back in with the same menu.

**Merge:** This is an entirely separate subject we won't deal with now
