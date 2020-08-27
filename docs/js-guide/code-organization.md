# Code Organization

TL;DR
- All JavaScript code should be in a .js file and encapsulated as a module using `hqDefine`.
- Dependencies should be imported in the `hqDefine` call for modules that support RequireJS (most of HQ), and using `hqImport` for modules that do not yet support non-RequireJS (web apps, app manager, reports).
- When creating class-like objects, use a functional inheritance pattern.

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
    lib/      <= Third-party code: This should be rare, since most third-party code should be coming from yarn
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

We're in the process of migrating to [RequireJS](https://requirejs.org/). Part of this process has included developing a lighter-weight alternative module system called `hqDefine`.

`hqDefine` serves as a stepping stone between legacy code and requirejs modules: it adds encapsulation but not
full-blown dependency management. **New code should be written to be compatible with RequireJS.** This is typically
easy; once familiar with the module patterns described below, see the [migration guide](https://github.com/dimagi/commcare-hq/blob/master/docs/js-guide/migrating.md#migrating-to-requirejs) for details on making sure your code will work with RequireJS.

Before diving into `hqDefine`, I want to talk first about the status quo
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
hqDefine('myapp/js/myModule', function () {
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
    var sayHi = hqImport('myapp/js/myModule').sayHi;
    // ... use sayHi ...
}
```

If you compare it to the above example, you'll notice that the
closure function itself is exactly the same. It's just being passed
to `hqDefine` instead of being called directly.

`hqDefine` is an intermediate step on the way to full support for AMD modules, which in HQ is implemented using RequireJS.
`hqDefine` checks whether or not it is on a page that uses AMD modules and then behaves in one of two ways:
* If the page has been migrated, so it uses AMD modules, `hqDefine` just delegates to `define`.
* If the page has not been migrated, `hqDefine` acts as a thin wrapper around the Crockford module pattern. `hqDefine` takes a function, calls it immediately, and puts it in a namespaced global; `hqImport` then looks up the module in that global.

In the first case, by handing control over to RequireJS, `hqDefine`/`hqImport` also act as a module *loader*.
But in the second case, they work only as a module *dereferencer*, so in order to use a module, it still needs to be included
as a `<script>` on your html page:

```html
<script src="{% static 'myapp/js/myModule.js' %}"></script>
```

Note that in the example above, the module name matches the end of the filename, the same name used to identify the file when using the `static` tag, but without the `js` extension. This is necessary for RequireJS to work properly. For consistency, all modules, regardless of whether or not they are yet compatible with RequireJS, should be named to match their filename.

`hqDefine` and `hqImport` provide a consistent interface for both migrated and unmigrated pages, and that interface is also consistent with RequireJS, making it easy to eventually "flip the switch" and remove them altogether once all code is compatible with RequireJS.

## Inheritance

We use a functional approach to inheritance, in this style:
```
var animal = function(options) {
  var self = {},
      location = 0,
      speed = 5;
  self.name = options.name;
  
  self.run = function(time) {
    location += time * speed;
  };
  
  self.getLocation = function() {
    return location;
  }
  
  return self;
};

var bear = animal({ name: 'Oso' });
bear.run(1);
// bear.name => "Oso"
// bear.getLocation() => 5
// bear.location => undefined

var bird = function(options) {
  var self = animal(options);
  
  self.fly = function(time) {
    // Flying is fast
    self.run(time);
    self.run(time);
  };
  
  return self;
};

var duck = bird({ name: 'Pato' });
duck.run(1);
duck.fly(1);
// duck.name => "Pato"
// duck.getLocation => 15
```
Note that:
- A class-like object is defined as a function that returns an instance.
- The instance is initialized to an empty object, or to an instance of the parent class if there is one.
- Create a private member by adding a local variable.
- Create a public member by attaching a variable to the instance that will be returned.
- Class name are `lowerFirstCamelCase`, distinct from `UpperFirstCamelCase` which is used for built-in objects like `Date` that require the `new` operator.

Avoid prototypical inheritance, which does not support information hiding as well.

Avoid classical-style inheritance (the `new` operator) because it also isn't great for information hiding and because forgetting to use `new` when creating an object can lead to nasty bugs.

Our approach to inheritance is heavily influenced by Crockford's _Javascript: The Good Parts_, which is good background reading.
