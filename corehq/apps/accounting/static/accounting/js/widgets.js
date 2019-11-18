hqDefine('accounting/js/widgets', [
    'jquery',
    'knockout',
    'underscore',
    'select2/dist/js/select2.full.min',
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

        self.init = function (initial) {
            var $field = $('form [name="' + self.fieldName + '"]');
            if ($field.attr('type') !== 'hidden') {
                if (initial) {
                    if (!_.isArray(initial)) {
                        initial = [{id: initial, text: initial}];
                    }

                    // Add a DOM option for each value, which select2 will pick up on change
                    _.each(initial, function (result) {
                        $field.append(new Option(result.text, result.id));
                    });

                    // Set the actual value; using an array works for both single and multiple selects
                    $field.val(_.pluck(initial, 'id'));
                }
                $field.select2({
                    minimumInputLength: 0,
                    placeholder: '',    // required for allowClear to work
                    allowClear: true,
                    ajax: {
                        delay: 150,
                        url: '',
                        dataType: 'json',
                        type: 'post',
                        data: function (params) {
                            return {
                                handler: 'select2_billing',
                                action: self.fieldName,
                                searchString: params.term,
                                existing: $('form [name="' + self.fieldName + '"]').val(),
                                additionalData: self.getAdditionalData(),
                            };
                        },
                    },
                    multiple: self.multiple,
                });
            }
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

        self.init = function (initial) {
            var $field = $('form [name="' + self.fieldName + '"]');
            if (initial) {
                if (!_.isArray(initial)) {
                    initial = [{id: initial, text: initial}];
                }

                // Add a DOM option for each value, which select2 will pick up on change
                _.each(initial, function (result) {
                    $field.append(new Option(result.text, result.id));
                });

                // Set the actual value; using an array works for both single and multiple selects
                $field.val(_.pluck(initial, 'id'));
            }
            $field.select2({
                tags: true,
                createTag: function (params) {
                    var term = params.term,
                        data = this.$element.select2("data");

                    // Prevent duplicates
                    var matchedData = $(data).filter(function () {
                        return this.text.localeCompare(term) === 0;
                    });

                    if (matchedData.length === 0 && self.utils.validateEmail(term)) {
                        return { id: term, text: term };
                    }
                },
                multiple: true,
                data: [],
                language: {
                    noResults: function () {
                        return self.validEmailText;
                    },
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
            handler.init(_.map($(input).data("initial"), function (e) {
                return {
                    id: e,
                    text: e,
                };
            }));
        });
        $(".accounting-email-select2").removeAttr('required');

        _.each($(".accounting-async-select2"), function (input) {
            var handler = asyncSelect2Handler($(input).attr("name"));
            handler.init();
        });

        _.each($(".accounting-country-select2"), function (el) {
            var country = asyncSelect2Handler('country'),
                data = $(el).data(),
                initial = [];
            if (data.countryCode) {
                initial = [{
                    id: data.countryCode,
                    text: data.countryName,
                }];
            }
            country.init(initial);
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
