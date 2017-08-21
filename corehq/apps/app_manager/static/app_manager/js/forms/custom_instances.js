/* globals ko */
hqDefine('app_manager/js/forms/custom_instances', function() {
    'use strict';

    var CustomInstance = function(instanceId, instancePath){
        var self = this;
        self.instanceId = ko.observable(instanceId || '');
        self.instancePath = ko.observable(instancePath || '');
    };

    var CustomInstances = function(){
        var self = this;
        self.customInstances = ko.observableArray();

        self.mapping = {
            customInstances: {
                create: function(options){
                    return new CustomInstance(options.data.instanceId, options.data.instancePath);
                },
            },
        };

        self.wrap = function(instances){
            return ko.mapping.fromJS(instances, self.mapping, self);
        };

        self.unwrap = function(){
            return ko.mapping.toJS(self);
        };

        self.addInstance = function(instance){
            instance = instance || {instanceId: null, instancePath: null};
            self.customInstances.push(
                new CustomInstance(instance.instanceId, instance.instancePath)
            );
        };

        self.removeInstance = function(instance){
            self.customInstances.remove(instance);
        };

        self.serializedCustomInstances = ko.computed(function(){
            return JSON.stringify(self.unwrap().customInstances);
        });

    };

    return new CustomInstances();

});
