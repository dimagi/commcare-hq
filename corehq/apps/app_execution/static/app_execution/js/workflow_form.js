hqDefine("app_execution/js/workflow_form", [
    'jquery',
    'knockout',
], function ($, ko) {
    let formModel = function () {
        let self = {};

        self.editMode = ko.observable("simple");
        self.simpleMode = ko.computed(function () {
            return self.editMode() === "simple";
        });
        self.toggleMode = function () {
            self.editMode(self.simpleMode() ? "advanced" : "simple");
        };

        return self;
    };

    $("#workflow-form").koApplyBindings(formModel());
});
