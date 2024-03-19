"use strict";
hqDefine('app_manager/js/forms/custom_instances', function () {
    'use strict';

    var customInstance = function (instanceId, instancePath) {
        var self = {};
        self.instanceId = ko.observable(instanceId || '');
        self.instancePath = ko.observable(instancePath || '');
        return self;
    };

    var customInstances = function () {
        var self = {};
        self.customInstances = ko.observableArray();

        self.mapping = {
            customInstances: {
                create: function (options) {
                    return customInstance(options.data.instanceId, options.data.instancePath);
                },
            },
        };

        self.wrap = function (instances) {
            return ko.mapping.fromJS(instances, self.mapping, self);
        };

        self.unwrap = function () {
            return ko.mapping.toJS(self);
        };

        self.addInstance = function (instance) {
            instance = instance || {instanceId: null, instancePath: null};
            self.customInstances.push(
                customInstance(instance.instanceId, instance.instancePath)
            );
        };

        self.removeInstance = function (instance) {
            self.customInstances.remove(instance);
        };

        self.serializedCustomInstances = ko.computed(function () {
            return JSON.stringify(self.unwrap().customInstances);
        });

        return self;
    };

    return customInstances();
});
