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
    
HQ's app manager only allows users to configure one level of nesting; that is, it does not allow for "grandchild" modules. Although CommCare mobile supports multiple levels of nesting, beyond two levels it quickly gets prohibitively complex for the user to understand the implications of their app design and for for HQ to `determine a logical set of session variables <https://github.com/dimagi/commcare-hq/blob/765bb4030d0923a4ae887aabecf688e72045dd7b/corehq/apps/app_manager/suite_xml/sections/entries.py#L366>`_ for every case. The modules could have all different case types, all the same, or a mix, and for modules that use the same case type, that case type may have a different meanings (e.g., a "person" case type that is sometimes a mother and sometimes a child), which all makes it difficult for HQ to determine the user's intended application design. See below for more on how session variables are generated with child modules.

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

Shadow Modules
--------------

A shadow module is a module that piggybacks on another module's commands (the "source" module). The shadow module has its own name, case list configuration, and case detail configuration, but it uses the same forms as its source module.

This is primarily for clinical workflows, where the case detail is a list of patients and the clinic wishes to be able to view differently-filtered queues of patients that ultimately use the same set of forms.

Shadow modules are behind the feature flag **Shadow Modules**.

Scope
~~~~~

The shadow module has its own independent:

- Name
- Menu mode (display module & forms, or forms only)
- Media (icon, audio)
- Case list configuration (including sorting and filtering)
- Case detail configuration

The shadow module inherits from its source:

- case type
- commands (which forms the module leads to)
- end of form behavior

Limitations
~~~~~~~~~~~

A shadow module can neither **be** a parent module nor **have** a parent module

A shadow module's source can be a parent module (the shadow will include a copy of the children), or have a parent module (the shadow will appear as a child of that same parent)

Shadow modules are designed to be used with case modules. They may behave unpredictably if given an advanced module or reporting module as a source.

Shadow modules do not necessarily behave well when the source module uses custom case tiles. If you experience problems, make the shadow module's case tile configuration exactly matches the source module's.

Entries
~~~~~~~

A shadow module duplicates all of its parent's entries. In the example below, m1 is a shadow of m0, which has one form. This results in two unique entries, one for each module, which share several properties.

.. code-block:: xml

    <entry>
        <form>
            http://openrosa.org/formdesigner/86A707AF-3A76-4B36-95AD-FF1EBFDD58D8
        </form>
        <command id="m0-f0">
            <text>
                <locale id="forms.m0f0"/>
            </text>
        </command>
    </entry>
    <entry>
        <form>
            http://openrosa.org/formdesigner/86A707AF-3A76-4B36-95AD-FF1EBFDD58D8
        </form>
        <command id="m1-f0">
            <text>
                <locale id="forms.m0f0"/>
            </text>
        </command>
    </entry>

Menu structure
~~~~~~~~~~~~~~

In the simplest case, shadow module menus look exactly like other module menus. In the example below, m1 is a shadow of m0. The two modules have their own, unique menu elements.

.. code-block:: xml

    <menu id="m0">
        <text>
            <locale id="modules.m0"/>
        </text>
        <command id="m0-f0"/>
    </menu>
    <menu id="m1">
        <text>
            <locale id="modules.m1"/>
            </text>
        <command id="m1-f0"/>
    </menu>
    

Menus get more complex when shadow modules are mixed with parent/child modules. In the following example, m0 is a basic module, m1 is a child of m0, and m2 is a shadow of m0. All three modules have `put_in_root=false` (see **Child Modules > Menu structure** above).  The shadow module has its own menu and also a copy of the child module's menu. This copy of the child module's menu is given the id `m1.m2` to distinguish it from `m1`, the original child module menu.

.. code-block:: xml

    <menu id="m0">
        <text>
            <locale id="modules.m0"/>
        </text>
        <command id="m0-f0"/>
    </menu>
    <menu root="m0" id="m1">
        <text>
            <locale id="modules.m1"/>
        </text>
        <command id="m1-f0"/>
    </menu>
    <menu root="m2" id="m1.m2">                                                                                                     <text>
            <locale id="modules.m1"/>
        </text>                                                                                                                     <command id="m1-f0"/>
    </menu>
    <menu id="m2">                                                                                                                  <text>
            <locale id="modules.m2"/>
        </text>                                                                                                                     <command id="m2-f0"/>
    </menu>
