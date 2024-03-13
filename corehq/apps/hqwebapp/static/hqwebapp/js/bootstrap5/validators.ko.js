hqDefine("hqwebapp/js/bootstrap5/validators.ko", [
    'jquery',
    'knockout',
    'knockout-validation/dist/knockout.validation.min', // needed for ko.validation
], function (
    $,
    ko
) {
    'use strict';

    ko.validation.init({
        errorMessageClass: 'invalid-feedback',
        errorElementClass: 'is-invalid',
        decorateElement: true,
        decorateInputElement: true,
    }, true);

    ko.validation.rules['emailRFC2822'] = {
        validator: function (val) {
            if (val === undefined || val.length === 0) return true;  // do separate validation for required
            var re = /(?:[a-z0-9!#$%&'*+\/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+\/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])$/;
            return re.test(val || '') && val.indexOf(' ') < 0;
        },
        message: gettext("Not a valid email"),
    };

    ko.validation.registerExtenders();

    /**
     * Use this handler to show bootstrap validation states on a form input when
     * your input's observable has been extended by Knockout Validation
     *
     * Pass in the following:
     * {
     *      validator: primary observable with validation,
     *      delayedValidator: de-coupled rate limited observable with validation (optional),
     *      successMessage: text (optional),
     *      checkingMessage: text (optional),
     * }
     *
     * delayedValidator is useful if you are doing async validation and want to decouple async validation from
     * other validators (perhaps for rate limiting). See Organisms > Forms in styleguide for example.
     *
     */
    ko.bindingHandlers.koValidationStateFeedback = {
        init: function (element, valueAccessor) {
            let options = valueAccessor(),
                successMessage = ko.unwrap(options.successMessage),
                checkingMessage = ko.unwrap(options.checkingMessage);
            $(element)
                .after($('<span />').addClass('valid-feedback').text(successMessage))
                .after($('<span />').addClass('validating-feedback')
                    .append($('<i class="fa fa-spin fa-spinner"></i>')).append(" " + (checkingMessage || gettext("Checking..."))))
                .after($('<span />').addClass('ko-delayed-feedback'));
        },
        update: function (element, valueAccessor) {
            let options = valueAccessor(),
                validatorVal = ko.unwrap(options.validator),
                isValid = false,
                isValidating = false,
                isDelayedValid;

            if (validatorVal === undefined) {
                return;
            }

            if (options.delayedValidator === undefined) {
                isValid = options.validator.isValid();
                isValidating = options.validator.isValidating !== undefined && options.validator.isValidating();
                if (isValid !== undefined && !isValid) $(element).addClass('is-invalid');
            } else {
                isValidating = options.validator.isValid() && options.delayedValidator.isValidating();

                isDelayedValid = options.delayedValidator.isValid();
                if (!isDelayedValid && !isValidating) {
                    $(element).addClass('is-invalid').removeClass('is-valid is-validating');
                    $(element).next('.ko-delayed-feedback')
                        .addClass('invalid-feedback').text(options.delayedValidator.error());
                } else {
                    $(element).next('.ko-delayed-feedback').removeClass('invalid-feedback').text("");
                }

                isValid = options.validator.isValid() && isDelayedValid;
            }

            if (isValidating) {
                $(element).removeClass('is-valid is-invalid').addClass('is-validating');
            } else {
                $(element).removeClass('is-validating');
            }

            if (isValid && !isValidating) {
                $(element).addClass('is-valid').removeClass('is-invalid is-validating');
            } else if (!isValid) {
                $(element).removeClass('is-valid');
            }
        },
    };
});
