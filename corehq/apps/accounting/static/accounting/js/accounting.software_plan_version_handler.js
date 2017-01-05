var SoftwarePlanVersionFormHandler = function (role, featureRates, productRates) {
    'use strict';
    var self = this;

    self.role = new PermissionsManager(role);
    self.featureRates = new RateAsyncManager(FeatureRate, featureRates);
    self.productRates = new RateAsyncManager(ProductRate, productRates);

    self.init = function () {
        self.role.init();
        self.featureRates.init();
        self.productRates.init();
    };
};


var RateAsyncManager = function (objClass, options) {
    'use strict';
    var self = this;

    self.handlerSlug = options.handlerSlug;

    self.error = ko.observable();
    self.showError = ko.computed(function () {
        return !! self.error();
    });

    self.objClass = objClass;
    self.rates = ko.observableArray();
    self.ratesString = ko.computed(function () {
        return JSON.stringify(_.map(self.rates(), function (obj){
            return obj.asJSON();
        }));
    });

    self.rateNames = ko.computed(function () {
        return _.map(self.rates(), function(rate) {
            return rate.name();
        });
    });

    self.select2 = new Select2RateHandler(options.select2Options, self.rateNames);

    self.init = function () {
        self.select2.init();
        var currentValue = JSON.parse(options.currentValue || '[]');
        self.rates(_.map(currentValue, function (data) {
            return new self.objClass(data);
        }));

    };

    self.rateType = ko.observable();

    self.createNew = function () {
        self.utils.sendToAsyncHandler('create', {
            name: self.select2.value(),
            rate_type: self.rateType()
        }, self.addRate);
    };

    self.apply = function () {
        self.utils.sendToAsyncHandler('apply', {
            rate_id: self.select2.value()
        }, self.addRate);
    };

    self.addRate = function (data) {
        self.rates.push(new self.objClass(data));
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
                    }
                }
            });
        }
    }
};

var PermissionsManager = function (options) {
    'use strict';
    var self = this;

    self.existingRoles = ko.observableArray();
    self.roleType = ko.observable(options.roleType);
    self.isRoleTypeNew = ko.computed(function () {
        return self.roleType() == 'new';
    });
    self.isRoleTypeExisting = ko.computed(function () {
        return self.roleType() == 'existing';
    });

    self.new = new NewRoleManager(self.existingRoles, options.newPrivileges);
    self.existing = new ExistingRoleManager(self.existingRoles, options.currentRoleSlug);

    self.init = function () {
        if (options.multiSelectField) {
            var multiselect_utils = hqImport('style/js/multiselect_utils');
            multiselect_utils.createFullMultiselectWidget(
                'id_' + options.multiSelectField.slug,
                options.multiSelectField.titleSelect,
                options.multiSelectField.titleSelected,
                options.multiSelectField.titleSearch
            );
        }
        self.existingRoles(_.map(options.existingRoles, function (data) {
            return new Role(data);
        }));
        $('#id_new_role_slug').on('keyup change', function (event) {
            var c = String.fromCharCode(event.keyCode);
            if (c.match(/\w/)) {
                var orig_val = $(this).val();
                $(this).val(orig_val.replace(' ', '_').replace('-','_'));
            }
        });
        $('#id_role_slug').select2();
        $('#roles form').submit(function (e) {
            if (self.new.hasMatchingRole() && self.isRoleTypeNew()) {
                self.existing.roleSlug(self.new.matchingRole().slug());
                $('#id_role_slug').select2('val', self.new.matchingRole().slug());
            }
        })
    };
};

var NewRoleManager = function (existingRoles, newPrivileges) {
    'use strict';
    var self = this;

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
};


var ExistingRoleManager = function (existingRoles, currentRoleSlug) {
    'use strict';
    var self = this;

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
        return _.isEmpty(self.selectedPrivileges())
    });
};


var BaseSelect2Handler = function (options, currentSelectionObj) {
    'use strict';
    var self = this;
    self.currentSelection = currentSelectionObj;
    self.fieldName = options.fieldName;
    self.value = ko.observable();

    self.clear = function () {
        var fieldInput = self.utils.getField();
        fieldInput.select2('val', '');
    };

    self.getHandlerSlug = function () {
        throw new Error('getHandlerSlug must be implemented;')
    };

    self.getExtraData = function () {
        return {}
    };

    self.processResults = function (response) {
        // override this if you want to do something special with the response.
        return response;
    };

    self.createNewChoice = function (term, selectedData) {
        // override this if you want the search to return the option of creating whatever
        // the user entered.
    };

    self.formatResult = function (result) {
        return result.text;
    };

    self.formatSelection = function (result) {
        return result.text;
    };

    self.getInitialData = function (element) {
        // override this if you want to format the value that is initially stored in the field for this widget.
    };

    self.utils = {
        getField: function () {
            return $('[name="' + self.fieldName + '"]');
        }
    };

    self.init = function () {
        var fieldInput = self.utils.getField();
        fieldInput.select2({
            minimumInputLength: 0,
            allowClear: true,
            ajax: {
                quietMillis: 150,
                url: '',
                dataType: 'json',
                type: 'post',
                data: function (term) {
                    var data = self.getExtraData(term);
                    data['handler'] = self.getHandlerSlug();
                    data['action'] = self.fieldName;
                    data['searchString'] = term;
                    return data;
                },
                results: self.processResults,
                500: function () {
                    self.error("Server encountered a problem. Please notify a dev.");
                }
            },
            createSearchChoice: self.createNewChoice,
            formatResult: self.formatResult,
            formatSelection: self.formatSelection,
            initSelection : function (element, callback) {
                if (element.val()) {
                    var data = self.getInitialData(element);
                    if (data) callback(data);
                }
            }
        });
        if (self.onSelect2Change) {
            fieldInput.on("change", self.onSelect2Change);
        }
    };
};

var Select2RateHandler = function (options, currentValue) {
    'use strict';
    BaseSelect2Handler.call(this, options, currentValue);

    var self = this;
    self.currentValue = currentValue;
    self.isNew = ko.observable(false);
    self.isExisting = ko.observable(false);

    self.getHandlerSlug = function () {
        return 'select2_rate';
    };

    self.getExtraData = function (term) {
        return {
            existing: self.currentValue()
        }
    };

    self.createNewChoice = function (term, selectedData) {
        // override this if you want the search to return the option of creating whatever
        // the user entered.
        var matching = _(selectedData).map(function (item) {
            return item.text;
        });
        if (matching.indexOf(term) === -1 && term) {
            return {id: term, text: term, isNew: true}
        }
    };

    self.formatResult = function (result) {
        if (result.isNew) {
            return '<span class="label label-success">New</span> ' + result.text;
        }
        return result.name + ' <span class="label">' + result.rate_type + '</span>';
    };

    self.formatSelection = function (result) {
        self.isNew(!!result.isNew);
        self.isExisting(!!result.isExisting);
        return result.text || (result.name + ' [' + result.rate_type + ']');
    };

    self.getInitialData = function (element) {
        return {id: element.val(), text: element.val()};
    };

    self.onSelect2Change = function (event) {
        if ($(this).val() == '') {
            self.isNew(false);
            self.isExisting(false);
        }
    };
};

Select2RateHandler.prototype = Object.create( BaseSelect2Handler.prototype );
Select2RateHandler.prototype.constructor = Select2RateHandler;


var Role = function (data) {
    'use strict';
    var self = this;

    self.privileges = ko.observableArray(_.map(data.privileges, function (priv) {
        return new Privilege(priv);
    }));
    self.privilegeSlugs = ko.computed(function () {
        return _.map(self.privileges(), function (priv) {
            return priv.slug();
        });
    });

    self.slug = ko.observable(data.slug);
    self.name = ko.observable(data.name);
    self.description = ko.observable(data.description);
};


var Privilege = function (data) {
    'use strict';
    var self = this;
    self.slug = ko.observable(data[0]);
    self.name = ko.observable(data[1]);
};


var FeatureRate = function (data) {
    'use strict';
    var self = this;

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
};


var ProductRate = function (data) {
    'use strict';
    var self = this;

    self.name = ko.observable(data.name);
    self.product_type = ko.observable(data.product_type);
    self.product_id = ko.observable(data.product_id);
    self.rate_id = ko.observable(data.rate_id);
    self.monthly_fee = ko.observable(data.monthly_fee);

    self.asJSON = function () {
        var result = {};
        _.each(['name', 'product_type', 'product_id', 'rate_id', 'monthly_fee'], function (field) {
            result[field] = self[field]();
        });
        return result;
    };
};
