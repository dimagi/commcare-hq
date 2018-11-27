/* global ko */
/* global django */
/* global zxcvbn */

ko.validation.rules['phone_number_val'] = {
    message: django.gettext("PHONE VALIDATION MESSAGE"),
};

ko.validation.registerExtenders();
