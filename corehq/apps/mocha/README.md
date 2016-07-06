Mocha Tests
===========

## Adding a new app to test

There are three steps to adding a new app to test:

  1. Add the app name to the `Gruntfile.js` file. Note: the app has to correspond to an actual Django app.
  2. Create a mocha template in `corehq/apps/<app>/templates/<app>/spec/mocha.html` to run tests. See an example on [here](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/app_manager/templates/app_manager/spec/mocha.html).
  3. Create tests that are included in the template in `corehq/apps/<app>/static/<app>/spec/`


## Creating an alternative configuration for an app

Occasionally there's a need to use a different mocha template to run tests for the same app. In order to create multiple configurations, specify the app in the `Gruntfile.js` like this:

```
<app>#<config>
```

Now mocha will look for that template in `corehq/apps/<app>/templates/<app>/spec/<config>/mocha.html`

The url to visit that test suite is `http://localhost:8000/mocha/<app>/<config>`
