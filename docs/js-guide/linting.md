# Linting

Our recommended linter is [ESLint](http://eslint.org/).
This is what
[dimagimon](https://confluence.dimagi.com/display/internal/Lint-Review+Service)
is currently running.

There is an `.eslintrc.js` file in the root of the commcare-hq repository which
defines the rules to check.

## Running ESLint locally
The best time to find out about a code error (or stylistic faux pas) is when
you type it out.  For this reason, you should run a linter locally.

```shell
# Install it through npm:
$ npm install -g eslint

# Try it out locally if you like
$ eslint path/to/file.js
```

### PyCharm
https://www.jetbrains.com/help/pycharm/2016.1/using-javascript-code-quality-tools.html?origin=old_help#ESLint

### Vim
#### NeoMake
[Install NeoMake](https://github.com/benekastah/neomake) if you haven't
already.
```
let g:neomake_javascript_enabled_makers = ['eslint']
```

#### Syntastic
[Install syntastic](https://github.com/scrooloose/syntastic) if you haven't
already.
```
let g:syntastic_javascript_checkers = ['eslint']
```

## Configuring our lint rules

ESLint is wildly configurable, and we will likely go through some iteration on
the specific ruleset we use.
[Full list of rules](http://eslint.org/docs/rules/).
[Configuring rules](http://eslint.org/docs/user-guide/configuring#configuring-rules)

Take a gander at `.eslintrc.js` in the root of the `commcare-hq` repo. We're
currently extending `"eslint:recommended"`, which is a defult set of rules.
This set of rules is overridden and added to in the `"rules"` entry.

### Global variables
We warn when ESLint detects undefined variables.  There are three ways to
address this.
 1. Use `hqdefine`
 2. Declare it as a global in the `.eslintrc.js`.  This should be done
    sparingly.
 3. Declare it as a global at the top of the javascript file
    ```
    /*global var1, var2*/
    ```
This treatment of global variables can also be helpful when converting stuff to
`hqdefine` - simply comment out everything in the `"globals"` object in
`.eslintrc.js`, and it'll warn you of any undefined variables.

### Turning off rules
Let's say you ran eslint on this code
```javascript
var obj = {
    foo: 3,
    foo: 5
};
```
You'd probably get an error like:
> Duplicate key 'foo'. (no-dupe-keys)

The rule then is `no-dupe-keys`.  You can look it up on the [rules
page](http://eslint.org/docs/rules/) for a description.

#### Disabling the rule globally
Disable the rule by adding an entry to the config like
```javascript
    "no-dupe-keys": ["off"]
```

#### Adding an exception
A foolish consistency is the hobgoblin of simple minds.  Sometimes it IS okay
to use `console.log`.  Here are a couple ways to say "yes, this IS okay".
```javascript
console.log('foo'); // eslint-disable-line no-console

// eslint-disable-next-line no-console
console.log('foo');
```
See the [docs](http://eslint.org/docs/user-guide/configuring#configuring-rules)
for more options.
