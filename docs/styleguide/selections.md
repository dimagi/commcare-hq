# Selections

This page demonstrates various **Selection Components** using the enhanced MkDocs Django plugin that reuses the existing styleguide infrastructure.

## Overview

A good rule of thumb when deciding what selection component to use is the following:

- **Select-Toggles** are good for selecting between a small list of items (2-5 items).
- **Select2s** are good for selective from a very large set of items, as it supports pagination.
- **Multiselects** are useful when the action involves moving items between two lists.

For any user-defined data, it's difficult to be certain how many items will be in the list. Even data sets that we might expect to be small—such as the number of forms in a module—might be large for certain projects. It's better to assume that a list will grow large and display it as some kind of dropdown where the options are a click away, rather than to assume it'll stay small and display all options on the page.

## Select-Toggle

On the occasions when a list is guaranteed to be short (2-5 items), consider displaying it as a toggle. This shows all options and only takes one click to select.

We use a custom toggle widget `<select-toggle>` that uses [Knockout Components](https://knockoutjs.com/documentation/component-overview.html) and is conceptually the same as a single-select dropdown. See [select_toggle.js](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/hqwebapp/static/hqwebapp/js/components/select_toggle.js) for full documentation.

There's also a `SelectToggle` widget for use with Forms, defined in [hqwebapp's widgets.py](https://github.com/dimagi/commcare-hq/blob/ab80b0017c12eb7fddb54bb20b2a186b07e8294f/corehq/apps/hqwebapp/widgets.py#L140-L160).

::: django-example-component styleguide/_includes/examples/bootstrap5/toggles.html :::

!!! info "Alternative Implementation"
    A few places in HQ use the same look and feel as the select toggle widget but have unique implementations. They generally use bootstrap's [button groups](https://getbootstrap.com/docs/5.3/components/button-group/) and also often include our own `btn-group-separated` class, which separates the buttons, making them easier to read and wrap better.

### Usage in Crispy Forms

In crispy forms, we can use the `SelectToggle` widget on a `ChoiceField`. If the crispy form is not being included inside a knockout model, `apply_bindings=True` must be specified in the widget's arguments. Otherwise, you can specify `ko_value`, as well as other options in `attrs`.

::: django-example-component styleguide/_includes/examples/bootstrap5/toggles_crispy.html :::

## Select2

For most lists, select2 is the way to go. It adds behavior to a normal `<select>` element. It supports either hard-coded static options or dynamic options fetched via ajax. It can support free text options, acting like an autocomplete, or can restrict users to a specific list of options. Beyond these major options, select2 supports many more specific features and styling options; see the [full documentation](https://select2.org/) for details.

We instantiate select2 in a number of different ways: manually with javascript, via knockout bindings, and by using CSS classes that certain javascript modules search for.

We also have a `select2` options for common behaviors like validating email addresses and displaying form questions. Before you add a new custom set of `select2` options, please look around and ask around for other parts of HQ that have similar behavior.

### Manual Setup

This is the most straightforward way of initializing a `select2` element.

::: django-example-component styleguide/_includes/examples/bootstrap5/select2_manual.html :::

A clearable version of that `select2` element:

::: django-example-component styleguide/_includes/examples/bootstrap5/select2_manual_allow_clear.html :::

#### Manual Setup with Crispy Forms

This is similar to the manual setup above, but using crispy forms to provide the form HTML.

::: django-example-component styleguide/_includes/examples/bootstrap5/select2_manual_crispy.html :::

### Referencing a CSS Class

We can automatically initialize a `select2` using the css class `hqwebapp-select2`, as long as the `hqwebapp/js/bootstrap5/widgets` module is present.

::: django-example-component styleguide/_includes/examples/bootstrap5/select2_css_class.html :::

This also applies to `<select multiple>` elements:

::: django-example-component styleguide/_includes/examples/bootstrap5/select2_css_class_multiple.html :::

#### Referencing the CSS Class in Crispy Forms

This is similar to the HTML-based setups above, but adding the `hqwebapp-select2` to `crispy.Field`'s `css_class` argument instead.

::: django-example-component styleguide/_includes/examples/bootstrap5/select2_css_class_crispy.html :::

### Dynamic Knockout Binding

We can also use the knockout binding `select2` to initialize a `select2`, with options provided by Knockout.

::: django-example-component styleguide/_includes/examples/bootstrap5/select2_ko_dynamic.html :::

#### Dynamic Knockout Binding with Crispy Forms

This is similar to the HTML-based setups above, except that an external script applies `koApplyBindings` to the `<form> id` (`<form>` can also be wrapped with a `<div>` with the same `id`). In order to apply the binding to the `ChoiceField` in crispy forms, the `data_bind` argument is used inside `crispy.Field`.

::: django-example-component styleguide/_includes/examples/bootstrap5/select2_ko_dynamic_crispy.html :::

### Static Knockout Binding

We can also initialize a `select2` with the `staticSelect2` Knockout Binding, where the options are pulled from `HTML` instead of Knockout. This is useful for `select2s` that have non-varying options but don't work with the `hqwebapp-select2` CSS class because they're inside a Knockout-controlled UI, so they aren't guaranteed to exist on page render.

::: django-example-component styleguide/_includes/examples/bootstrap5/select2_ko_static.html :::

#### Static Knockout Binding with Crispy Forms

This is similar to the HTML-based setups above, except that an external script applies `koApplyBindings` to the `<form> id` (`<form>` can also be wrapped with a `<div>` with the same `id`).

::: django-example-component styleguide/_includes/examples/bootstrap5/select2_ko_static_crispy.html :::

### Autocomplete Knockout Binding

To initialize a `select2` to autocomplete select suggestions, use the `autocompleteSelect2` Knockout binding. The difference between this binding and the original `select2`, is the ability to enter free text.

::: django-example-component styleguide/_includes/examples/bootstrap5/select2_ko_autocomplete.html :::

#### Autocomplete Knockout Binding with Crispy Forms

This is similar to the HTML-based setups above, except that an external script applies `koApplyBindings` to the `<form> id` (`<form>` can also be wrapped with a `<div>` with the same `id`).

::: django-example-component styleguide/_includes/examples/bootstrap5/select2_ko_autocomplete_crispy.html :::

### Crispy Forms Select2Ajax Widget

It's also possible to use `select2` that fetches its options asynchronously in crispy forms using the `Select2Ajax` `widget`. This is extremely useful for selecting from a large data set, like Mobile Workers or Locations. A very simplified example is below.

!!! info "Implementation Note"
    Note that you will need a view to `POST` queries to with this widget. It's recommended to explore how `Select2Ajax` is currently being used in HQ.

::: django-example-component styleguide/_includes/examples/bootstrap5/select2_ajax_crispy.html :::

## Multiselect

This is a custom widget we built. It can be useful in situations where the user is adding and removing items from one list to another and wants to be able to see both the included and excluded items.

!!! warning "Use with Caution"
    **Be cautious adding it to new pages!** Be sure that the visual weight and potential learning curve is worthwhile for the workflow you're creating. It's more complicated than a dropdown and takes up much more space.

::: django-example-component styleguide/_includes/examples/bootstrap5/multiselect.html :::

### Optional Properties

In addition to the optional title properties, the following properties can be useful in situations where more control is needed.

- **disableModifyAllActions**—defaults to `false`, useful when the preferred workflow is to disable the ability to select and remove all items at once.
- **willSelectAllListener**—provides an opportunity to execute code prior to all items being selected

### Use in Crispy Forms

This is similar to the manual setup above, but using crispy forms to provide the form HTML.

::: django-example-component styleguide/_includes/examples/bootstrap5/multiselect_crispy.html :::

## Other Selection Interactions

There are several other interactions used on HQ to select items from a list, however use of these options should be **limited** compared to the options above.

### Standard Select Elements

There's nothing inherently wrong with standard `<select>` elements, but since so many dropdowns use `select2`, `<select>` elements without this styling create visual inconsistency. It should typically be trivial to turn a standard `<select>` element into a `select2`.

!!! info "Long Lists"
    Standard `<select>` elements do interfere with usability when their list of options gets long. For instance, with 15+ items, it becomes difficult to find and select an item. Therefore, long lists in particular should be switched to `select2`.

### Lists of Checkboxes

Like standard HTML select elements, there's nothing inherently wrong with these, but because we don't use them often, they're bad for a consistent user experience.

### At.js

At.js is a library for mentioning people in comments. It's the basis for **easy references** in Form Builder, used in the xpath expression builder. Form builder also uses it for autocomplete behavior (form builder doesn't have `select2` available).

Case List Explorer use At.js for creating the advanced search query by allowing the user to search and reference case properties as they build a query.

Both Form Builder and Case List Explorer use At.js in a powerful way: to build queries or expressions with advanced syntax. At.js **should not** be used for simple autocomplete or select behavior.

## Usage Guidelines

### When to Use Each Component

- **Select-Toggle**: Use for 2-5 options that are always visible and require single selection
- **Basic Select2**: Use for medium-sized datasets (10-100 options) with single selection
- **Select2 Multiple**: Use for medium-sized datasets requiring multiple selections
- **Select2 with Autocomplete**: Use for large datasets where users need to search/filter
- **Multiselect**: Use when users need to move items between "available" and "selected" lists

### Accessibility Considerations

All selection components should:
- Support keyboard navigation
- Have proper ARIA labels
- Provide clear visual feedback for selection states
- Work with screen readers

### Performance Notes

For very large datasets (1000+ options):
- Use Select2 with remote data loading
- Implement pagination in the backend
- Consider using autocomplete to reduce initial load time
