/* global ko */
/* global django */

ko.validation.rules['emailRFC2822'] = {
    validator: function (val) {
        if (val === undefined || val.length === 0) return true;  // do separate validation for required
        var re = /(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])$/;
        return re.test(val || '') && val.indexOf(' ') < 0;
    },
    message: django.gettext("Not a valid email"),
};

ko.validation.registerExtenders();

/**
 * Use this handler to show bootstrap validation states on a form input when
 * your input's observable has been extended by KnockoutValidation.
 *
 * Pass in the following:
 * {
 *      validator: observableWithValidation,
 *      delayedValidator: rateLimitedObservableWithValidation,
 * }
 *
 * delayedValidator is optional. Useful if you are doing async validation.
 *
 * You can see initial usage of this in registration/js/new_user.ko.js
 */
ko.bindingHandlers.koValidationStateFeedback = {
    init: function (element) {
        $(element).after($('<span />').addClass('fa form-control-feedback'));
    },
    update: function (element, valueAccessor) {
        var options = valueAccessor(),
            $feedback = $(element).next('.form-control-feedback'),
            $formGroup = $(element).parent('.form-group');

        var validatorVal = ko.unwrap(options.validator);

        // reset formGroup
        $formGroup
            .addClass('has-feedback')
            .removeClass('has-success has-error has-warning');

        // reset feedback
        $feedback
            .removeClass('fa-check fa-remove fa-spin fa-spinner');

        if (validatorVal === undefined) {
            return;
        }
        var isValid = (
            (options.validator.isValid() && options.delayedValidator === undefined) ||
            (options.validator.isValid() && options.delayedValidator !== undefined && options.delayedValidator.isValid())
        );

        if (isValid) {
            $feedback.addClass("fa-check");
            $formGroup.addClass("has-success");
        } else if (validatorVal !== undefined) {
            $feedback.addClass("fa-remove");
            $formGroup.addClass("has-error");
        }
    },
};
