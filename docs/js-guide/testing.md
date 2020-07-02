# Testing

## Best Practices

Writing good tests in javascript is similar to writing good tests in any other language. There are a few best practices that are more pertinent to javascript testing.

### Mocking

Mock any dependency with `sinon.js`. `sinon.js` is extremely easy to use.
TODO

### No AJAX calls
TODO

### Avoid asynchronous tests
TODO

## Setup

In order to run the javascript tests you'll need to install the required npm packages:

    $ yarn install

It's recommended to install grunt globally in order to use grunt from the command line:

    $ npm install -g grunt
    $ npm install -g grunt-cli

In order for the tests to run the __development server needs to be running on port 8000__.

## Running tests from the command line

To run all javascript tests in all the apps:

    $ grunt test

To run the javascript tests for a particular app run:

    $ grunt test:<app_name> // (e.g. grunt test:app_manager)

To list all the apps available to run:

    $ grunt list


## Running tests from the browser

To run tests from the browser (useful for debugging) visit this url:

```
http://localhost:8000/mocha/<app_name>
```

Occasionally you will see an app specified with a `/`, like `app_manager/b3`. The string after `/` specifies that the test uses an alternate configuration. To visit this suite in the browser go to:

```
http://localhost:8000/mocha/<app_name>/<config>  // (e.g. http://localhost:8000/mocha/app_manager/b3)
```

## Adding a new app to test

There are three steps to adding a new app to test:

  1. Add the app name to the `Gruntfile.js` file. Note: the app has to correspond to an actual Django app.
  2. Create a mocha template in `corehq/apps/<app>/templates/<app>/spec/mocha.html` to run tests. See an example on [here](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/app_manager/templates/app_manager/spec/mocha.html).
  3. Create tests that are included in the template in `corehq/apps/<app>/static/<app>/spec/`


## Creating an alternative configuration for an app

Occasionally there's a need to use a different mocha template to run tests for the same app. An example of this is if the app uses javascript that depends on bootstrap2 libraries and javascript that depends on bootstrap3 libraries. In order to create multiple configurations, specify the app in the `Gruntfile.js` like this:

```
<app>/<config>  // (e.g. app_manager/b3)
```

Now mocha will look for that template in `corehq/apps/<app>/templates/<app>/spec/<config>/mocha.html`

The url to visit that test suite is `http://localhost:8000/mocha/<app>/<config>`

