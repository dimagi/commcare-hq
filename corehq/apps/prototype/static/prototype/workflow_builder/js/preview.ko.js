/* global _ */
/* global $ */
/* global ko */

hqDefine('prototype.workflow_builder.preview', function () {
   'use strict';
    var module = {};
    var utils = hqImport('prototype.workflow_builder.utils');

    module.AppPreview = function (app) {
        var self = this;
        self.curScreenIndex = ko.observable(0);
        self.screens = ko.observableArray();
        self.isShown = ko.observable(true);

        self.init = function () {
            var screenA = new ScreenSelectWorkflow(app);
            self.screens.push(screenA);
        };

        self.toggleShown = function () {
            self.isShown(!self.isShown());
        };

        self.screenTemplate = function (screen) {
            return screen.templateId();
        };

        self.screenA = new ScreenSelectWorkflow(app);
    };

    var ScreenSelectWorkflow = function (app) {
        var self = this;
        self.templateId = ko.observable('ko-template-screen-a');
        self.orderedWorkflows = ko.computed(function () {
            return _.sortBy(app.workflows(), function (wf) {
                return wf.distance();
            });
        });
    };

    return module;
});
