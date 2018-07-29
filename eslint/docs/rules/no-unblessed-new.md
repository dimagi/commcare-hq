# Disallow new except for specified objects. (no-unblessed-new)

Created to help make inheritance style more consistent.

## Rule Details

This rule aims to move away from use of the `new` operator except when working with built-in Javascript or
third-party code that requires it.

Examples of **incorrect** code for this rule, assuming options is `['Thing']`:

```js

var thing = new OtherThing();

```

Examples of **correct** code for this rule, assuming options is `['Thing']`:

```js

var thing = new Thing();

```

### Options

Accepts an array of identifiers. These are classes that may be created with `new`.

## When Not To Use It

When you wish to allow pseudo-classical inheritance.
