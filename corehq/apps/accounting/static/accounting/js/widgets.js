hqDefine('accounting/js/widgets', [
    'jquery',
    'knockout',
    'underscore',
    'select2-3.5.2-legacy/select2',
], function (
    $,
    ko,
    _
) {
    var asyncSelect2Handler = function (field, multiple) {
        'use strict';
        var self = {};

        self.fieldName = field;
        self.multiple = !! multiple;

        self.init = function () {
            var $field = $('form [name="' + self.fieldName + '"]');
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
                                existing: $('form [name="' + self.fieldName + '"]').val().split(','),
                                additionalData: self.getAdditionalData(),
                            };
                        },
                        results: function (data) {
                            return data;
                        },
                    },
                    multiple: self.multiple,
                    initSelection: self.initSelection,
                });
            }
        };

        self.initSelection = function (element, callback) {
            var data = (self.multiple) ? billingInfoUtils.getMultiResultsFromElement(element) :
                billingInfoUtils.getSingleResultFromElement(element);
            callback(data);
        };

        self.getAdditionalData = function () {
            return null;
        };

        return self;
    };

    var emailSelect2Handler = function (field) {
        'use strict';
        var self = {};

        self.fieldName = field;
        self.validEmailText = gettext("Please enter a valid email.");

        self.init = function () {
            $('form [name="' + self.fieldName + '"]').select2({
                createSearchChoice: function (term, data) {
                    var matchedData = $(data).filter(function () {
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
                },
            });
        };

        self.utils = {
            validateEmail: function (email) {
                // from http://stackoverflow.com/questions/46155/validate-email-address-in-javascript
                var re = /^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/; // eslint-disable-line no-useless-escape
                return re.test(email);
            },
        };

        return self;
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
        },
    };

    var adjustBalanceFormModel = function () {
        var self = {};
        self.adjustmentType = ko.observable("current");
        self.showCustomAmount = ko.computed(function () {
            return self.adjustmentType() === 'credit';
        }, self);

        return self;
    };

    $(function () {
        _.each($(".accounting-email-select2"), function (input) {
            var handler = emailSelect2Handler($(input).attr("name"));
            handler.init();
        });
        $(".accounting-email-select2").removeAttr('required');

        _.each($(".accounting-async-select2"), function (input) {
            var handler = asyncSelect2Handler($(input).attr("name"));
            handler.init();
        });

        _.each($(".accounting-country-select2"), function () {
            var country = asyncSelect2Handler('country');
            country.initSelection = function (element, callback) {
                var data = {
                    text: element.data('countryname'),
                    id: element.val(),
                };
                callback(data);
            };
            country.init();
        });

        _.each($('.ko-adjust-balance-form'), function (form) {
            $(form).koApplyBindings(adjustBalanceFormModel());
        });
    });

    return {
        asyncSelect2Handler: asyncSelect2Handler,
        emailSelect2Handler: emailSelect2Handler,
    };
});
