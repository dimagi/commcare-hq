var SoftwarePlanVersionFormHandler = function (featureRates, productRates) {
    'use strict';
    var self = this;

    self.featureRates = new RatesManager(FeatureRate, featureRates);
    self.productRates = new RatesManager(ProductRate, productRates);

    self.init = function () {
        self.featureRates.init();
        self.productRates.init();
    };
};

var RatesManager = function (rate_object, options) {
    'use strict';
    var self = this;

    self.rate_object = rate_object;
    self.asyncHandler = options.async_handler;
    self.rateType = ko.observable();
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
    self.select2 = new Select2FieldHandler(options.field_name, options.select2_handler, self.objectNames);

    self.init = function () {
        self.select2.init();
        var current_objects = $.parseJSON(options.current_value || '[]');
        self.objects(_.map(current_objects, function (data) {
            return new self.rate_object(data);
        }));

    };

    self.createNew = function () {
        self.utils.sendToAsyncHandler(self.asyncHandler, 'create', {
            name: self.select2.object_id(),
            rate_type: self.rateType()
        }, self.addRate);
    };

    self.apply = function () {
        self.utils.sendToAsyncHandler(self.asyncHandler, 'apply', {
            rate_id: self.select2.object_id()
        }, self.addRate);
    };

    self.addRate = function (data) {
        self.objects.push(new self.rate_object(data));
    };

    self.removeRate = function (rate) {
        self.objects.remove(rate);
    };

    self.utils = {
        sendToAsyncHandler: function (handler, action, data, handleSuccess) {
            // todo handle errors with the request itself
            data['handler'] = handler;
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
                }
            });
        }
    }
};

var Select2FieldHandler = function (fieldName, asyncHandler, existingObjects) {
    'use strict';
    var self = this;

    self.fieldName = fieldName;
    self.asyncHandler = asyncHandler;
    self.object_id = ko.observable();
    self.existingObjects = existingObjects;
    self.isNew = ko.observable(false);
    self.isExisting = ko.observable(false);

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
                    return {
                        handler: 'select2_rate',
                        action: self.fieldName,
                        searchString: term,
                        existing: self.existingObjects()
                    };
                },
                results: function (data) {
                    return {
                        results: data
                    };
                }
            },
            createSearchChoice: function (term, data) {
                var matching = _(data).map(function (item) {
                    return item.text;
                });
                if (matching.indexOf(term) === -1 && term) {
                    return {id: term, text: term, isNew: true}
                }
            },
            formatResult: function (result) {
                if (result.isNew) {
                    return '<span class="label label-success">New</span> ' + result.text;
                }
                return result.name + ' <span class="label">' + result.rate_type + '</span>';
            },
            formatSelection: function (result) {
                self.isNew(!!result.isNew);
                self.isExisting(!!result.isExisting);
                return result.text || (result.name + ' [' + result.rate_type + ']');
            },
            initSelection : function (element, callback) {
                if (element.val()) {
                    var data = {id: element.val(), text: element.val()};
                    callback(data);
                }
            }
        });
        fieldInput.on("change", function(e) {
            if ($(this).val() == '') {
                self.isNew(false);
                self.isExisting(false);
            }
        });
    };

    self.clear = function () {
        var fieldInput = self.utils.getField();
        fieldInput.select2('val', '');
    };

    self.utils = {
        getField: function () {
            return $('[name="' + self.fieldName + '"]');
        }
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
