/* global _kmq */
/* global KM */
/* global $ */

/** Use this module to trigger the July 2016 Sign Up form A/B test
 * usage:
 *
 * 1) pass the selector for the element that directs the user to the signup page
 * as $signupElem.
 *
 * 2) pass the final action attribute ('action' or 'href'), defaults to 'href'.
 * This is the attribute that gets the value stored in data-actionA (old url)
 * and data-actionB (new url). Make sure your tested element has these attributes.
 */

hqDefine('registration/js/signup_ab.js', function () {
    'use strict';
    var ab = {};
    var _private = {};
    _private.TEST_NAME = 'Signup Form July 2016';
    ab.VAR_A = 'old';
    ab.VAR_B = 'new';

    ab.init = function ($signupElem, actionAttr) {
        actionAttr = actionAttr || 'href';  // defaults
        _kmq.push(function () {
            var testVar = KM.ab(_private.TEST_NAME, [ab.VAR_A, ab.VAR_B]);
            var action = $signupElem.attr((testVar === ab.VAR_B) ? 'data-actionB' : 'data-actionA');
            $signupElem.attr(actionAttr, action);
        });
    };

    ab.redirectIfNotMatching = function (matchType, redirectUrl) {
        _kmq.push(function () {
            var testVar = KM.ab(_private.TEST_NAME, [ab.VAR_A, ab.VAR_B]);
            if (testVar !== matchType) {
                window.location = redirectUrl;
            }
        });
    };

    ab.registerClickCreateAccount = function (testType) {
        _kmq.push(["trackClick", "click_create_account", "Clicked Create Account (" + testType + ")"]);
    };

    ab.registerSuccess = function (testType) {
        _kmq.push(["trackClick", "account_create_successful", "Account Creation was Successful (" + testType + ")"]);
    };

    return ab;
});
