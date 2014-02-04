var SoftwarePlanVersionFormHandler = function (role, featureRates, productRates) {
    'use strict';
    var self = this;
    console.log(role);
    console.log(featureRates);
    console.log(productRates);

//    self.role = new RoleAsyncManager(Role, Select2RoleHandler, role);
    self.featureRates = new RateAsyncManager(FeatureRate, Select2RateHandler, featureRates);
    self.productRates = new RateAsyncManager(ProductRate, Select2RateHandler, productRates);

    self.init = function () {
//        self.role.init();
        self.featureRates.init();
        self.productRates.init();
    };
};

var BaseAsyncManager = function (objClass, select2Class, options) {
    'use strict';
    var self = this;

    self.objClass = objClass;
    self.select2Class = select2Class;
    self.handlerSlug = options.handlerSlug;

    self.error = ko.observable();
    self.showError = ko.computed(function () {
        return !! self.error();
    });

    self.objects = ko.observableArray();
    self.objectsValue = ko.computed(function () {
        return JSON.stringify(_.map(self.objects(), function (obj){
            return obj.asJSON();
        }));
    });

    self.objectNames = ko.computed(function () {
        return _.map(self.objects(), function(object) {
            return object.name();
        });
    });
    self.select2 = new self.select2Class(options.select2Options, self.objectNames);

    self.init = function () {
        self.select2.init();
        var currentValue = $.parseJSON(options.currentValue || '[]');
        self.objects(_.map(currentValue, function (data) {
            return new self.objClass(data);
        }));

    };

    self.utils = {
        sendToAsyncHandler: function (action, data, handleSuccess) {
            // todo handle errors with the request itself
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

var RateAsyncManager = function (objClass, select2Class, options) {
    'use strict';
    BaseAsyncManager.call(this, objClass, select2Class, options);
    var self = this;
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
        self.objects.push(new self.objClass(data));
    };

    self.removeRate = function (rate) {
        self.objects.remove(rate);
    };
};

RateAsyncManager.prototype = Object.create( BaseAsyncManager.prototype );
RateAsyncManager.prototype.constructor = RateAsyncManager;


var RoleAsyncManager = function (objClass, options) {
    'use strict';
    BaseAsyncManager.call(this, objClass, options);
    var self = this;
};

RoleAsyncManager.prototype = Object.create( BaseAsyncManager.prototype );
RoleAsyncManager.prototype.constructor = RoleAsyncManager;


var BaseSelect2Handler = function (options, currentValue) {
    'use strict';
    var self = this;
    self.currentValue = currentValue;
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
        console.log(fieldInput);
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
    self.isNew = ko.observable(false);
    self.isExisting = ko.observable(false);

    self.getHandlerSlug = function () {
        return 'select2_rate';
    };

    self.getExtraData = function (getHandlerSlug) {
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


var Select2RoleHandler = function (options, currentValue) {
    'use strict';
    BaseSelect2Handler.call(this, options, value);

    var self = this;
    self.getHandlerSlug = function () {
        return 'select2_role';
    };
};

Select2RoleHandler.prototype = Object.create( BaseSelect2Handler.prototype );
Select2RoleHandler.prototype.constructor = Select2RoleHandler;

var Role = function (data) {
    'use strict';
    var self = this;

    self.slug = ko.observable(data.slug);
    self.name = ko.observable(data.name);
    self.description = ko.observable(data.description);
    self.parameters = ko.observable(data.parameters);

    self.asJSON = function () {
        var result = {};
        _.each(['slug', 'name', 'description', 'parameters'], function (field) {
            result[field] = self[field]();
        });
        return result;
    };
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
