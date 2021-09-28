# Inheritance

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

## Moving from classical inheritance to functional

Most of our code uses functional inheritance, while some of it uses classical inheritance. We don't have an active
plan to replace all classical inheritance with functional, but if you have a reason to chang a particular classical class,
it can often be converted to a functional style fairly mechanically:

- In the class definition, make sure the instance is initialized to an empty object instead of `this`. There's usually a `var self = this;` line that should be switched to `var self = {};`
- Throughout the class definition, make sure the code is consistently using `self` instead of `this`
- Make sure the class definition returns `self` at the end (typically it won't return anything)
- Update class name from `UpperCamelCase` to `lowerCamelCase`
- Remove `new` operator from anywhere the class is instantiated

[Sample pull request](https://github.com/dimagi/commcare-hq/pull/19938)

Code that actually manipulates the prototype needs more thought.
