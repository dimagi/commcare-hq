hqDefine('accounting/js/billing_info_handler', [
    'jquery',
    'underscore',
    'select2-3.5.2-legacy/select2',
], function (
    $,
    _
) {
    var AsyncSelect2Handler = function (field, multiple) {
        'use strict';
        var self = this;

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

    };

    var EmailSelect2Handler = function (field) {
        'use strict';
        var self = this;
        self.fieldName = field;
        self.validEmailText = django.gettext("Please enter a valid email.");

        self.init = function () {
            $('form [name="' + self.fieldName + '"]').select2({
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
                },
            });
        };

        self.utils = {
            validateEmail: function (email) {
                // from http://stackoverflow.com/questions/46155/validate-email-address-in-javascript
                var re = /^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
                return re.test(email);
            },
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
        },
    };

    $(function() {
        _.each($(".accounting-email-select2"), function(input) {
            var handler = new EmailSelect2Handler($(input).attr("name"));
            handler.init();
        });
        $(".accounting-email-select2").removeAttr('required');

        _.each($(".accounting-async-select2"), function(input) {
            var handler = new AsyncSelect2Handler($(input).attr("name"));
            handler.init();
        });

        _.each($(".accounting-country-select2"), function(form) {
            var country = new AsyncSelect2Handler('country');
            country.initSelection = function (element, callback) {
                var data = {
                    text: element.data('countryname'),
                    id: element.val(),
                };
                callback(data);
            };
            country.init();
        });
    });

    return {
        AsyncSelect2Handler: AsyncSelect2Handler,
        EmailSelect2Handler: EmailSelect2Handler,
    };
});
