# Linting

Our recommended linter is [ESLint](http://eslint.org/).
This is what
our [Stickler configuration](https://github.com/dimagi/commcare-hq/blob/679d3ca7cf81d7808b6792a72046cedd891ed62f/.stickler.yml#L10)
uses.

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

PyCharm has different ways of setting this up depending on the version.

- [Instructions for 2016.1](https://www.jetbrains.com/help/pycharm/2016.1/using-javascript-code-quality-tools.html?origin=old_help#ESLint)
- [Instructions for 2017.3](https://www.jetbrains.com/help/pycharm/2017.3/eslint.html)

If you get errors you may need to [downgrade ESLint to version 5](https://intellij-support.jetbrains.com/hc/en-us/community/posts/360004195120-TypeError-this-cliEngine-is-not-a-constructor).
This appears to be an issue on all versions of PyCharm prior to 2019.1.3.

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

The [.eslintrc.js](https://github.com/dimagi/commcare-hq/blob/master/.eslintrc.js) file in the root of the commcare-hq repository defines the rules to check.

While this configuration is fairly stable, see the [docs](https://eslint.org/docs/user-guide/configuring#configuring-rules) for help should you need to update it.

### Looking up rules
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

#### Adding an exception
A foolish consistency is the hobgoblin of simple minds.  Sometimes it IS okay
to use `console.log`.  Here are a couple ways to say "yes, this IS okay".
```javascript
console.log('foo'); // eslint-disable-line no-console

// eslint-disable-next-line no-console
console.log('foo');
```
See the [docs](https://eslint.org/docs/user-guide/configuring#disabling-rules-with-inline-comments)
for more options to disable rules for on a case by case basis.
