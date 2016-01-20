Advanced App Features
=====================

See ``corehq.apps.app_manager.suite_xml.SuiteGenerator`` and ``corehq.apps.app_manager.xform.XForm`` for code.

Child Modules
-------------
In principle child modules is very simple. Making one module a child of another
simply changes the ``menu`` elements in the *suite.xml* file. For example in the
XML below module ``m1`` is a child of module ``m0`` and so it has its ``root``
attribute set to the ID of its parent.

.. code-block:: xml

    <menu id="m0">
        <text>
            <locale id="modules.m0"/>
        </text>
        <command id="m0-f0"/>
    </menu>
    <menu id="m1" root="m0">
        <text>
            <locale id="modules.m1"/>
        </text>
        <command id="m1-f0"/>
    </menu>


Menu structure
~~~~~~~~~~~~~~
As described above the basic menu structure is quite simple however there is one property in particular
that affects the menu structure: *module.put_in_root*

This property determines whether the forms in a module should be shown under the module's own menu item or
under the parent menu item:

+-------------+-------------------------------------------------+
| put_in_root | Resulting menu                                  |
+=============+=================================================+
| True        | id="<parent menu id>"                           |
+-------------+-------------------------------------------------+
| False       | id="<module menu id>" root="<parent menu id>"   |
+-------------+-------------------------------------------------+

**Notes:**

- If the module has no parent then the parent is *root*.
- *root="root"* is equivalent to excluding the *root* attribute altogether.


Session Variables
~~~~~~~~~~~~~~~~~

This is all good and well until we take into account the way the
`Session <https://github.com/dimagi/commcare/wiki/Suite20#the-session>`_ works on the mobile
which "prioritizes the most relevant piece of information to be determined by the user at any given time".

This means that if all the forms in a module require the same case (actually just the same session IDs) then the
user will be asked to select the case before selecting the form. This is why when you build a module
where *all forms require a case* the case selection happens before the form selection.

From here on we will assume that all forms in a module have the same case management and hence require the same
session variables.

When we add a child module into the mix we need to make sure that the session variables for the child module forms match
those of the parent in two ways, matching session variable names and adding in any missing variables.

Matching session variable names
...............................

For example, consider the session variables for these two modules:

**module A**::

    case_id:            load mother case

**module B** child of module A::

    case_id_mother:     load mother case
    case_id_child:      load child case

You can see that they are both loading a mother case but are using different session variable names.

To fix this we need to adjust the variable name in the child module forms otherwise the user will be asked
to select the mother case again:

    *case_id_mother* -> *case_id*

**module B** final::

    case_id:            load mother case
    case_id_child:      load child case

Inserting missing variables
...........................
In this case imagine our two modules look like this:

**module A**::

    case_id:            load patient case
    case_id_new_visit:  id for new visit case ( uuid() )

**module B** child of module A::

    case_id:            load patient case
    case_id_child:      load child case

Here we can see that both modules load the patient case and that the session IDs match so we don't
have to change anything there.

The problem here is that forms in the parent module also add a ``case_id_new_visit`` variable to the session
which the child module forms do not. So we need to add it in:

**module B** final::

    case_id:            load patient case
    case_id_new_visit:  id for new visit case ( uuid() )
    case_id_child:      load child case

Note that we can only do this for session variables that are automatically computed and
hence does not require user input.
