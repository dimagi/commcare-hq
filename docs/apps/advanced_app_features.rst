App Navigation Features
=======================

Navigation in CommCare is oriented around form entry. The goal of each CommCare session is to complete a form.
Menus and case lists are tools for gathering the necessary data required to enter a particular form.
App manager gives app builders direct control over many parts of their app's UI, but the exact sequence of screens
a user sees is *indirectly* configured.

Based on app configuration, HQ builds a ``suite.xml`` file that acts as a blueprint for the app. It outlines what
forms are available to fill out, where they fit, and what data (like cases) they will need to function. CommCare
interprets this configuration to decide which screens to show to the user and in what order.

Much of the complexity of app manager code, and of building apps, comes from inferences HQ makes while building the
suite file, especially around determining the set of data required for each form. These features that influence,
but don't directly control, the suite also influence each other, in ways that may not be obvious. The following
features are particularly prone to interact unexpectedly and should be tested together when any significant change
is made to any of them:

#. Display Only Forms
#. Select Parent First
#. End of Form Navigation and Form Linking
#. Child Modules
#. Shadow Modules

Several of these features are simple from an app builder's perspective, but they require HQ to "translate" UI
concepts into suite concepts.  Other features force the app builder to understand suite concepts, so they may
be challenging for app builders to learn but are less prone to interacting poorly with other features:

#. Case search, which maps fairly cleanly to the ``<remote-request>`` element (except when using the
   ``USH_INLINE_SEARCH`` flag).
#. Advanced modules

Display Only Forms
------------------
Display only forms is deceptively simple. This setting causes a module's forms to be displayed directly in the
parent menu (either the parent module's menu or the root CommCare menu), instead of the user needing to explicitly
select the menu's name. This can be a UX efficiency gain.

However, quite a lot of suite generation is structured around modules, and using display only forms means that
modules no longer map cleanly to ``<menu>`` elements. This means that modules using display only forms can't be
"destinations" in their own right, so they don't work with end of form navigation, form linking, or smart links.
It also complicates menu construction, raising issues like how to deal with module display conditions when the
module doesn't have a dedicated ``<menu>``.

Select Parent First
-------------------
When the "select parent first" setting is turned on for a module, the user is presented with a case list for
the **parent** case type. The user selects a case from this list and is then given another case list limited to
children of that parent. The user can select any other module in the app that uses the parent case type to use as
the configuration for this parent case list.

This setting is controlled by ``ModuleBase.parent_select`` and has a dedicated model, ``ParentSelect``.
The suite implementation is small: HQ adds a ``parent_id`` datum to the module's ``<entry>`` blocks and a filter to the
main ``case_id`` datum's nodeset to filter it to children of the parent:
``[index/parent=instance('commcaresession')/session/data/parent_id]``.

This is easy to confuse with parent/child modules (see below), which affect the suite's ``<menu>`` elements and can
affect datum generation.

The feature flag ``NON_PARENT_MENU_SELECTION`` allows the user to use any module as the "parent" selection, and it
does not use the additional nodeset filter. This allows for more generic two-case-list workflows.

End of Form Navigation and Form Linking
---------------------------------------
These features allow the user to select a destination for the user to be automatically navigated to after filling
out a particular form. To support this, HQ needs to figure out how to get to the requested destination, both the
actions taken (user selecting a form or menu) and the data needed (which needs to be pulled from somewhere,
typically the session, in order to automatically navigate the user instead of asking them to provide it).

End of form navigation ("EOF nav") allows for a couple of specific locations, such as going back to the form's module or its
parent module. EOF nav also has a "previous screen" option this is particularly fragile, since it requires HQ to
replicate CommCare's UI logic.

Form linking, which is behind the ``FORM_LINK_WORKFLOW`` flag, allows the user to select a form as the destination.
Form linking allows the user to link to multiple forms, depending on the value of an XPath expression.

Most forms can be linked "automatically", meaning that it's easy for HQ to determine what datums are needed.
See the
`auto_link <https://github.com/dimagi/commcare-hq/blob/b7c88d4127feeb0ebc17c7df3211fb523a900f6f/corehq/apps/app_manager/views/forms.py#L919-L950>`_
logic for implementation.
For other forms, HQ pushes the burden of figuring out datums towards the user, requiring them to provide an XPath
expression for each datum.

EOF nav and form linking config is stored in ``FormBase.post_form_workflow``. In the suite, it's implemented as a
`stack <https://github.com/dimagi/commcare-core/wiki/SessionStack>`_ in the form's ``<entry>`` block.
For details, see docs on ``WorkflowHelper``.

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
HQ will also update the references in expressions to match the changes in variable names.
See ``corehq.apps.app_manager.suite_xml.sections.entries.EntriesHelper.add_parent_datums`` for implementation.

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


**Note:**
If you have a case_id in both module A and module B, and you wish to access the ID of the case selected in
parent module within an expression like the case list filter, then you should use ``parent_id``
instead of ``case_id``

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

A shadow module's source can **be** a parent module. The shadow will automatically create a shadow version of any child modules as required.

A shadow module's source can **have** a parent module. The shadow will appear as a child of that same parent.

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


Legacy Child Shadow Behaviour
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Prior to August 2020 shadow modules whose source was a parent had inconsistent behaviour.

The child-shadows were not treated in the same manner as other shadows - they inherited everything from their source, which meant they could never have their own case list filter, and were not shown in the UI. This was confusing. A side-effect of this was that display-only forms were not correctly interpreted by the phone. The ordering of child shadow modules also used to be somewhat arbitrary, and so some app builders had to find workarounds to get the ordering they wanted. Now in V2, what you see is what you get.

Legacy (V1) style shadow modules that have children can be updated to the new behaviour by clicking "Upgrade" on the settings page. This will create any real new shadow-children, as required. This will potentially rename the identifier for all subsequent modules (i.e. `m3` might become `m4` if a child module is added above it), which could lead to issues if you have very custom XML references to these modules anywhere. It might also change the ordering of your child shadow modules since prior to V2, ordering was inconsistent. All of these things should be easily testable once you upgrade. You can undo this action by reverting to a previous build.

If the old behaviour is desired for any reason, there is a feature flag "V1 Shadow Modules" that allows you to make old-style modules.
