# eslint-plugin-eslint-dimagi

Dimagi-specific ESLint rules.
Intended for developers of [CommCareHQ](https://github.com/dimagi/commcare-hq).

## Installation

You'll first need to install [ESLint](http://eslint.org):

```
$ yarn add eslint --save-dev
```

Next, install `eslint-plugin-eslint-dimagi`:

```
$ yarn add eslint-plugin-eslint-dimagi --save-dev
```

**Note:** If you installed ESLint globally (using the `-g` flag) then you must also install `eslint-plugin-eslint-dimagi` globally.

## Usage

Add `eslint-dimagi` to the plugins section of your `.eslintrc` configuration file. You can omit the `eslint-plugin-` prefix:

```json
{
    "plugins": [
        "eslint-dimagi"
    ]
}
```


Then configure the rules you want to use under the rules section.

```json
{
    "rules": {
        "eslint-dimagi/rule-name": 2
    }
}
```

## Supported Rules

* no-unblessed-new: Disallows use of the `new` keyword except with specified object types.





