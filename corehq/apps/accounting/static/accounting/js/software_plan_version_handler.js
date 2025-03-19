"use strict";
hqDefine("accounting/js/software_plan_version_handler", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/select2_handler',
    'hqwebapp/js/multiselect_utils',
    'select2/dist/js/select2.full.min',
], function (
    $,
    ko,
    _,
    initialPageData,
    select2Handler,
    multiselectUtils
) {
    $(function () {
        var planVersionFormHandler = softwarePlanVersionFormHandler(
            initialPageData.get('role'),
            initialPageData.get('feature_rates'),
            initialPageData.get('product_rates')
        );
        $('#roles').koApplyBindings(planVersionFormHandler);
        planVersionFormHandler.init();
    });

    var softwarePlanVersionFormHandler = function (role, featureRates, productRates) {
        var self = {};

        self.role = permissionsManager(role);
        self.featureRates = rateAsyncManager(featureRate, featureRates);
        self.productRates = rateAsyncManager(productRate, productRates);

        self.init = function () {
            self.role.init();
            self.featureRates.init();
            self.productRates.init();
        };

        return self;
    };

    var rateAsyncManager = function (objClass, options) {
        var self = {};

        self.handlerSlug = options.handlerSlug;

        self.error = ko.observable();
        self.showError = ko.computed(function () {
            return !! self.error();
        });

        self.objClass = objClass;
        self.rates = ko.observableArray();
        self.ratesString = ko.computed(function () {
            return JSON.stringify(_.map(self.rates(), function (obj) {
                return obj.asJSON();
            }));
        });

        self.rateNames = ko.computed(function () {
            return _.map(self.rates(), function (rate) {
                return rate.name();
            });
        });

        self.select2 = select2RateHandler(options.select2Options, self.rateNames);

        self.init = function () {
            self.select2.init();
            var currentValue = JSON.parse(options.currentValue || '[]');
            self.rates(_.map(currentValue, function (data) {
                return self.objClass(data);
            }));

        };

        self.rateType = ko.observable();

        self.createNew = function () {
            self.utils.sendToAsyncHandler('create', {
                name: self.select2.value(),
                rate_type: self.rateType(),
            }, self.addRate);
        };

        self.apply = function () {
            self.utils.sendToAsyncHandler('apply', {
                rate_id: self.select2.value(),
            }, self.addRate);
        };

        self.addRate = function (data) {
            self.rates.push(self.objClass(data));
        };

        self.removeRate = function (rate) {
            self.rates.remove(rate);
        };

        self.utils = {
            sendToAsyncHandler: function (action, data, handleSuccess) {
                data['handler'] = self.handlerSlug;
                data['action'] = action;
                $.ajax({
                    dataType: 'json',
                    url: '',
                    type: 'post',
                    data: data,
                    success: function (response) {
                        if (response.success && handleSuccess) {
                            handleSuccess(response.data);
                        }
                        self.error(response.error);
                        self.select2.clear();
                    },
                    statusCode: {
                        500: function () {
                            self.error("Server encountered a problem. Please notify a dev.");
                        },
                    },
                });
            },
        };

        return self;
    };

    var permissionsManager = function (options) {
        var self = {};

        self.existingRoles = ko.observableArray();
        self.roleType = ko.observable(options.roleType);
        self.isRoleTypeNew = ko.computed(function () {
            return self.roleType() === 'new';
        });
        self.isRoleTypeExisting = ko.computed(function () {
            return self.roleType() === 'existing';
        });

        self.new = newRoleManager(self.existingRoles, options.newPrivileges);
        self.existing = existingRoleManager(self.existingRoles, options.currentRoleSlug);

        self.init = function () {
            if (options.multiSelectField) {
                multiselectUtils.createFullMultiselectWidget('id_' + options.multiSelectField.slug, {
                    selectableHeaderTitle: options.multiSelectField.titleSelect,
                    selectedHeaderTitle: options.multiSelectField.titleSelected,
                    searchItemTitle: options.multiSelectField.titleSearch,
                });
            }
            self.existingRoles(_.map(options.existingRoles, function (data) {
                return role(data);
            }));
            $('#id_new_role_slug').on('keyup change', function (event) {
                var c = String.fromCharCode(event.keyCode);
                if (c.match(/\w/)) {
                    var original = $(this).val();
                    $(this).val(original.replace(' ', '_').replace('-','_'));
                }
            });
            $('#id_role_slug').select2();
            $('#roles form').submit(function () {
                if (self.new.hasMatchingRole() && self.isRoleTypeNew()) {
                    self.existing.roleSlug(self.new.matchingRole().slug());
                    $('#id_role_slug').val(self.new.matchingRole().slug()).trigger('change');
                }
            });
        };

        return self;
    };

    var newRoleManager = function (existingRoles, newPrivileges) {
        var self = {};

        self.existingRoles = existingRoles;

        self.privileges = ko.observableArray(newPrivileges);
        self.matchingRole = ko.computed(function () {
            // If the set of current privileges match the privileges of an existing role, return that existing role.
            var existingRole = null;
            _.each(self.existingRoles(), function (role) {
                var isEquivalent = _.isEmpty(role.privilegeSlugs()) && _.isEmpty(self.privileges());
                if (isEquivalent || (!_.isEmpty(role.privilegeSlugs())
                        && _.isEmpty(_(role.privilegeSlugs()).difference(self.privileges()))
                        && role.privilegeSlugs().length === self.privileges().length)) {
                    existingRole = role;
                }
            });
            return existingRole;
        });
        self.matchingPrivileges = ko.computed(function () {
            if (self.matchingRole()) {
                return self.matchingRole().privileges();
            }
            return [];
        });
        self.allowCreate = ko.computed(function () {
            return !_.isEmpty(self.privileges()) && _.isEmpty(self.matchingPrivileges());
        });
        self.hasMatchingRole = ko.computed(function () {
            return !_.isNull(self.matchingRole());
        });

        return self;
    };


    var existingRoleManager = function (existingRoles, currentRoleSlug) {
        var self = {};

        self.existingRoles = existingRoles;

        self.roleSlug = ko.observable(currentRoleSlug);
        self.selectedRole = ko.computed(function () {
            var selectedRole = null;
            _.each(self.existingRoles(), function (role) {
                if (role.slug() === self.roleSlug()) {
                    selectedRole = role;
                }
            });
            return selectedRole;
        });
        self.selectedPrivileges = ko.computed(function () {
            if (self.selectedRole()) {
                return self.selectedRole().privileges();
            }
            return [];
        });
        self.hasNoPrivileges = ko.computed(function () {
            return _.isEmpty(self.selectedPrivileges());
        });

        return self;
    };


    var baseSelect2Handler = select2Handler.baseSelect2Handler;
    var select2RateHandler = function (options, currentValue) {
        var self = baseSelect2Handler(options);

        self.currentValue = currentValue;
        self.isNew = ko.observable(false);
        self.isExisting = ko.observable(false);

        self.getHandlerSlug = function () {
            return 'select2_rate';
        };

        self.getExtraData = function () {
            return {
                existing: self.currentValue(),
            };
        };

        self.createTags = true;
        self.createNewChoice = function (params) {
            var term = $.trim(params.term),
                matching = _.pluck(this.$element.select2("data"), 'text');
            if (matching.indexOf(term) === -1 && term) {
                return {
                    id: term,
                    text: term,
                    isNew: true,
                };
            }
        };

        self.templateResult = function (result) {
            if (result.isNew) {
                return '<span class="label label-success">New</span> ' + result.text;
            }
            if (_.has(result, 'rate_type')) {
                return result.name + ' <span class="label">' + result.rate_type + '</span>';
            } else {
                return result.name;
            }

        };

        self.templateSelection = function (result) {
            self.isNew(!!result.isNew);
            self.isExisting(!!result.isExisting);
            if (_.has(result, 'rate_type')) {
                return result.text || (result.name + ' [' + result.rate_type + ']');
            } else {
                return result.text || result.name;
            }
        };

        self.getInitialData = function (element) {
            return {id: element.val(), text: element.val()};
        };

        self.onSelect2Change = function () {
            if (!$(this).val()) {
                self.isNew(false);
                self.isExisting(false);
            }
        };

        return self;
    };

    select2RateHandler.prototype = Object.create(baseSelect2Handler.prototype);
    select2RateHandler.prototype.constructor = select2RateHandler;


    var role = function (data) {
        var self = {};

        self.privileges = ko.observableArray(_.map(data.privileges, function (priv) {
            return privilege(priv);
        }));
        self.privilegeSlugs = ko.computed(function () {
            return _.map(self.privileges(), function (priv) {
                return priv.slug();
            });
        });

        self.slug = ko.observable(data.slug);
        self.name = ko.observable(data.name);
        self.description = ko.observable(data.description);

        return self;
    };


    var privilege = function (data) {
        var self = {};
        self.slug = ko.observable(data[0]);
        self.name = ko.observable(data[1]);
        return self;
    };


    var featureRate = function (data) {
        var self = {};

        self.name = ko.observable(data.name);
        self.feature_type = ko.observable(data.feature_type);
        self.feature_id = ko.observable(data.feature_id);
        self.rate_id = ko.observable(data.rate_id);
        self.monthly_fee = ko.observable(data.monthly_fee);
        self.per_excess_fee = ko.observable(data.per_excess_fee);
        self.monthly_limit = ko.observable(data.monthly_limit);

        self.isPerExcessVisible = ko.computed(function () {
            return self.feature_type() !== 'SMS';
        });

        self.asJSON = function () {
            var result = {};
            _.each(['name', 'feature_type', 'feature_id', 'rate_id', 'monthly_fee',
                'per_excess_fee', 'monthly_limit'], function (field) {
                result[field] = self[field]();
            });
            return result;
        };

        return self;
    };


    var productRate = function (data) {
        var self = {};

        self.name = ko.observable(data.name);
        self.product_rate_id = ko.observable(data.product_rate_id);
        self.rate_id = ko.observable(data.rate_id);
        self.monthly_fee = ko.observable(data.monthly_fee);

        self.asJSON = function () {
            var result = {};
            _.each(['name', 'product_rate_id', 'rate_id', 'monthly_fee'], function (field) {
                result[field] = self[field]();
            });
            return result;
        };

        return self;
    };
});
