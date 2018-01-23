# Code Organization

TL;DR
- put code in .js files, not in html
- use `hqDefine` and `hqImport` as your module system
- you'll see various versions of modules based on manually
  restricting the global footprint of a file.
  This has been done using varying degrees of discipline,
  and you should always feel comfortable converting these to `hqDefine`
- avoid global variables like the plague

For those of you looking for a little more from this page,
please keep reading.

## Static Files Organization

JavaScript files belong in the `static` directory of a Django app,
which we structure as follows:

```
myapp/
  static/myapp/
    css/
    font/
    images/
    js/       <= JavaScript
    less/
    lib/      <= Third-party code: This should be rare, since most third-party code should be coming from bower
    spec/     <= JavaScript tests
    ...       <= May contain other directories for data files, i.e., `json/`
  templates/myapp/
    mytemplate.html
```


## Using Django Template Tags and Variables

Keeping JavaScript in dedicated files has numerous benefits over inline script blocks:
- Better readability due to languages being separate
- Easier code reuse
- Browser caching of js files
- Better integration with JavaScript tools

The most common historical reason we've put JavaScript into Django templates has been to 
pass data from the server to a script. We now have infrastructure to access server data
from .js files; see [Server Integration Patterns](./integration-patterns.md) for more detail.

There are a few places we do intentionally use script blocks, such as configuring less.js in CommCareHQ's
main template, `hqwebapp/base.html`. These are places where there's just a few lines
of code that's truly independent of the rest of the site's JavaScript. They are rare.

There are also a number of Django templates with legacy `<script>` blocks. By and large,
these are being "externalized" into separate files as we modernize our JavaScript. See
[Migrating](./migrating.md#migrating-inline-script-blocks-to-js-files) for guidance migrating inline JavaScript to an external .js file.


## Module patterns

We talk about JavaScript modules, but (at least pre-ES6) JavaScript
has no built in support for modules.
It's easy to say that, but think about how crazy that is.
If this were Python, it would mean your program's main file has to
directly list all of the files that will be needed, in the correct order,
and then the files share state through global variables. That's insane.

And it's also JavaScript. Fortunately, there are things you can do to
enforce and respect the boundaries that keep us sane by following
one of a number of patterns.
Many full-blown module systems have been created for in-browser JavaScript,
including `require.js` and more recently `system.js`,
but for the time being we've decided to go with a lighter weight alternative.
Before diving into that, I want to talk first about the status quo
convention for sanity with no module system.
As we'll describe, it's a step down from our current preferred choice,
but it's still miles ahead of having no convention at all,
and you're likely to encounter it throughout our code base for some time yet.

### The Crockford Pattern

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
MYNAMESPACE.myModule = (function () {
    // things inside here are private
    var myPrivateGreeting = "Hello";
    // unless you put them in the return object
    var sayHi = function (name) {
        console.log(myPrivateGreeting + " from my module, " + name);
    };
    return {
        sayHi: sayHi,
        favoriteColor: “blue”,
    };
}());
```

This uses a pattern so common in JavaScript that it has it's own
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
    favoriteColor: “blue”,
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

### hqDefine

There are many great module systems out there, so why did we write our own?
The answer's pretty simple: while it's great to start with
require.js or system.js, getting from here to there is nearly impossible
without some intermediate. Imagine the amount of times you see
`$` or `_` (for jQuery or underscore.js) throughout our codebase;
that alone would make it nearly impossible to refactor all our code at once
to fit into one of these admittedly super nice systems.

Using the above example again, using `hqDefine`,
you'd write your file like this:

```javascript
// file commcare-hq/corehq/apps/myapp/static/myapp/js/myModule.js
hqDefine('myapp/js/myModule.js', function () {
    // things inside here are private
    var myPrivateGreeting = "Hello";
    // unless you put them in the return object
    var sayHi = function (name) {
        console.log(myPrivateGreeting + " from my module, " + name);
    };
    return {
        sayHi: sayHi,
        favoriteColor: “blue”,
    };
});
```

and when you need it in another file

```javascript
// some other file
function () {
    var sayHi = hqImport('myapp/js/myModule.js').sayHi;
    // ... use sayHi ...
}
```

If you compare it to the above example, you'll notice that the
closure function itself is exactly the same. It's just being passed
to `hqDefine` instead of being called directly.

If you're working on a page that doesn't inherit
from the main template, you'll have to include
```html
<script src="{% static 'hqwebapp/js/hqModules.js' %}"></script>
```
to use `hqDefine` and `hqImport`.

A note about using modules on an html page.
Whereas any other module system is also a module *loader*,
`hqImport` is just a module *dereferencer*; what I mean by that is that
in order to use a module, it still needs to be included
as a `<script>` on your html page:

```html
<script src="{% static 'myapp/js/myModule.js' %}"></script>
```

In fact, `hqImport` and `hqDefine`
are really a very thin wrapper aroudn the Crockford module pattern.
In the end `hqDefine` does just take a function, call it immediately,
and put the value in a namespaced but globally retrievable place;
and `hqImport` just looks it up from that place.
But what it gives us is extreme consistency by the most correct thing
also the easiest.

For a summary, please scroll back up and see the TL;DR section.
