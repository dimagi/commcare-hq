# Historical Background on Module Patterns

This page discusses the evolution of HQ's javascript module usage.
For practical documentation on writing modules, see [Managing Dependencies](https://github.com/dimagi/commcare-hq/blob/master/docs/js-guide/dependencies.md).

We talk about JavaScript modules, but (at least pre-ES6) JavaScript
has no built in support for modules.
It's easy to say that, but think about how crazy that is.
If this were Python, it would mean your program's main file has to
directly list all of the files that will be needed, in the correct order,
and then the files share state through global variables. That's insane.

And it's also JavaScript. Fortunately, there are things you can do to
enforce and respect the boundaries that keep us sane by following
one of a number of patterns.

We're in the process of migrating to [RequireJS](https://requirejs.org/). Part of this process has included developing a lighter-weight alternative module system called `hqDefine`.

`hqDefine` serves as a stepping stone between legacy code and requirejs modules: it adds encapsulation but not
full-blown dependency management. New code is written in RequireJS, but `hqDefine` exists to support
legacy code that does not yet use RequireJS.

Before diving into `hqDefine`, I want to talk first about the status quo convention for sanity with no module system.
As we'll describe, it's a step down from our current preferred choice,
but it's still miles ahead of having no convention at all.

## The Crockford Pattern

The Crockford module pattern was popularized in Douglas Crockford's
classic 2008 book _JavaScript: The Good Parts_.
(At least that's how we heard about it here at Dimagi.)
It essentially has two parts.

1. The first and more important of the two parts is to
   *limit the namespace footprint of each file to a single variable*
   using a closure (`(function () { /* your code here */ }());`).
2. The second is to pick a single global namespace that you "own"
   (at Yahoo where he worked, theirs was `YAHOO`; ours is `COMMCAREHQ`)
   and assign all your modules to properties
   (or properties of properties, etc.)
   of that one global namespace.

Putting those together, it looks something like this:

```javascript
MYNAMESPACE.myModule = function () {
    // things inside here are private
    var myPrivateGreeting = "Hello";
    // unless you put them in the return object
    var sayHi = function (name) {
        console.log(myPrivateGreeting + " from my module, " + name);
    };
    return {
        sayHi: sayHi,
        favoriteColor: "blue",
    };
}();
```

This uses a pattern so common in JavaScript that it has its own
acronym "IIFE" for "Immediately Invoked Function Expression".
By wrapping the contents of the module in a function expression,
you can use variables and functions local to your module
and inaccessible from outside it.

I should also note that within our code, we've largely only adopted
the first of the two steps;
i.e. we do not usually expose our modules under `COMMCAREHQ`,
but rather as a single module `MYMODULE` or `MyModule`.
Often we even slip into exposing these "public" values
(`sayHi` and `favoriteColor` in the example above) directly as globals,
and you can see how looseness in the application of this pattern
can ultimately degenerate into having barely any system at all.
Notably, however, exposing modules as globals or even individual functions
as globals—but while wrapping their contents in a closure—
is still enormously preferable to being unaware of the convention
entirely. For example, if you remove the closure from the example above
(**don't do this**), you get:

```javascript
/* This is a toxic example, do not follow */

// actually a global
var myPrivateGreeting = "Hello";
// also a global
var sayHi = function (name) {
    console.log(myPrivateGreeting + " from my module, " + name);
};
// also a global
myModule = {
    sayHi: sayHi,
    favoriteColor: "blue",
};
```

In this case, `myPrivateGreeting` (now poorly named), `sayHi`,
and `myModule` would now be in the global namespace
and thus can be directly referenced _or overwritten_, possibly unintentionally, by any other JavaScript run on the same page.

Despite being a great step ahead from nothing,
this module pattern falls short in a number of ways.

1. It relies too heavily on programmer discipline,
   and has too many ways in which it is easy to cut corners,
   or even apply incorrectly with good intentions
2. If you use the `COMMCAREHQ.myJsModule` approach,
   it's easy to end up with unpredictable naming.
3. If you nest properties like `COMMCAREHQ.myApp.myJsModule`,
   you need boilerplate to make sure `COMMCAREHQ.myApp` isn't `undefined`.
   We never solved this properly and everyone just ended up avoiding it
   by not using the `COMMCAREHQ` namespace.
4. From the calling code, especially without using the `COMMCAREHQ`
   namespace, there's little to cue a reader as to where a function or
   module is coming from;
   it's just getting plucked out of thin (and global) air

This is why we are now using our own lightweight module system,
described in the next sesion.

## hqDefine

There are many great module systems out there, so why did we write our own?
The answer's pretty simple: while it's great to start with
require.js or system.js, with a code base HQ's size,
getting from here to there is nearly impossible
without an intermediate step.

Using the above example again, using `hqDefine`,
you'd write your file like this:

```javascript
// file commcare-hq/corehq/apps/myapp/static/myapp/js/myModule.js
hqDefine('myapp/js/myModule', function () {
    // things inside here are private
    var myPrivateGreeting = "Hello";
    // unless you put them in the return object
    var sayHi = function (name) {
        console.log(myPrivateGreeting + " from my module, " + name);
    };
    return {
        sayHi: sayHi,
        favoriteColor: "blue",
    };
});
```

and when you need it in another file

```javascript
// some other file
function () {
    var sayHi = hqImport('myapp/js/myModule').sayHi;
    // ... use sayHi ...
}
```

If you compare it to the above example, you'll notice that the
closure function itself is exactly the same. It's just being passed
to `hqDefine` instead of being called directly.

`hqDefine` is an intermediate step on the way to full support for AMD modules, which in HQ is implemented using RequireJS.
`hqDefine` checks whether or not it is on a page that uses AMD modules and then behaves in one of two ways:
* If the page has been migrated, meaning it uses AMD modules, `hqDefine` just delegates to `define`.
* If the page has not been migrated, `hqDefine` acts as a thin wrapper around the Crockford module pattern. `hqDefine` takes a function, calls it immediately, and puts it in a namespaced global; `hqImport` then looks up the module in that global.

In the first case, by handing control over to RequireJS, `hqDefine`/`hqImport` also act as a module *loader*.
But in the second case, they work only as a module *dereferencer*, so in order to use a module, it still needs to be included
as a `<script>` on your html page:

```html
<script src="{% static 'myapp/js/myModule.js' %}"></script>
```

Note that in the example above, the module name matches the end of the filename, the same name used to identify the file when using the `static` tag, but without the `js` extension. This is necessary for RequireJS to work properly. For consistency, all modules, regardless of whether or not they are yet compatible with RequireJS, should be named to match their filename.

`hqDefine` and `hqImport` provide a consistent interface for both migrated and unmigrated pages, and that interface is also consistent with RequireJS, making it easy to eventually "flip the switch" and remove them altogether once all code is compatible with RequireJS.
