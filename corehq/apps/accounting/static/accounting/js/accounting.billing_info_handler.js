var BillingContactInfoHandler = function (valid_email_text) {
    'use strict';
    var self = this;

    self.country = new AsyncSelect2Handler('country');
    self.country.initSelection = function (element, callback) {
        var data = {
            text: element.data('countryname'),
            id: element.val()
        };
        callback(data);
    };
    self.emails = new EmailSelect2Handler('email_list', valid_email_text);
    self.active_accounts = new AsyncSelect2Handler('active_accounts');

    self.init = function () {
        self.country.init();
        self.emails.init();
        self.active_accounts.init();
    };
};

var AsyncSelect2Handler = function (field, multiple) {
    'use strict';
    var self = this;

    self.fieldName = field;
    self.multiple = !! multiple;

    self.init = function () {
        $(function () {
            var $field = $('.hq-content [name="' + self.fieldName + '"]');
            if ($field.attr('type') !== 'hidden') {
                $field.select2({
                    minimumInputLength: 0,
                    allowClear: true,
                    ajax: {
                        quietMillis: 150,
                        url: '',
                        dataType: 'json',
                        type: 'post',
                        data: function (term) {
                            return {
                                handler: 'select2_billing',
                                action: self.fieldName,
                                searchString: term,
                                existing: $('.hq-content [name="' + self.fieldName + '"]').val().split(','),
                                additionalData: self.getAdditionalData()
                            };
                        },
                        results: function (data) {
                            return data;
                        }
                    },
                    multiple: self.multiple,
                    initSelection: self.initSelection
                });
            }
        });
    };

    self.initSelection = function (element, callback) {
        var data = (self.multiple) ? billingInfoUtils.getMultiResultsFromElement(element) :
            billingInfoUtils.getSingleResultFromElement(element);
        callback(data);
    };

    self.getAdditionalData = function () {
        return null;
    };

};

var EmailSelect2Handler = function (field, valid_email_text) {
    'use strict';
    var self = this;

    self.fieldName = field;
    self.validEmailText = valid_email_text;

    self.init = function () {
        $(function () {
            $('.hq-content [name="' + self.fieldName + '"]').select2({
                createSearchChoice: function (term, data) {
                    var matchedData = $(data).filter(function() {
                        return this.text.localeCompare(term) === 0;
                    });

                    var isEmailValid = self.utils.validateEmail(term);

                    if (matchedData.length === 0 && isEmailValid) {
                        return { id: term, text: term };
                    }
                },
                multiple: true,
                data: [],
                formatNoMatches: function () {
                    return self.validEmailText;
                },
                initSelection: function (element, callback) {
                    callback(billingInfoUtils.getMultiResultsFromElement(element));
                }
            });
        })
    };

    self.utils = {
        validateEmail: function (email) {
            // from http://stackoverflow.com/questions/46155/validate-email-address-in-javascript
            var re = /^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
            return re.test(email);
        }
    };
};

var billingInfoUtils = {
    getMultiResultsFromElement: function (element) {
        var data = $(element).val();
        return _.map(data.split(','), function (email) {
            return {id: email, text: email };
        });
    },
    getSingleResultFromElement: function (element) {
        var value = $(element).val();
        return {id: value, text: value};
    }
};
