How to Deploy
=============

Before every deploy, the various indexes on prod, mostly in couchdb,
must be updated. Strictly speaking this only has to be run
when an index is changed; for example, if you change or add a new couchdb view,
but as a precaution it should always be run before deploy.

.. code-block:: bash

    fab production preindex_views

Once preindexing has finished (you can check the futon/cloudant status page),
you can deploy using the following command:

.. code-block:: bash

    fab production deploy

This deploys whatever's in the latest master on github (not your local version).

Hotfix deploys
--------------

A hotfix deploy updates only the python code, restarting the services
that rely on it.

.. code-block:: bash

    fab production hotfix_deploy

Deploying another branch
------------------------

Sometimes you want to get a single urgent fix in
without deploying all of master.
In a situation like this, you can deploy straight from a branch.
(It is a good idea to then merge that branch into master as well.)

To deploy branch my_fix, use the following command:


.. code-block:: bash

    fab production deploy --set code_branch=my_fix

This should be used rarely, and is most often done
in conjunction with a hotfix deploy.

Note that again, the branch being deployed is the version on github,
not your local version.