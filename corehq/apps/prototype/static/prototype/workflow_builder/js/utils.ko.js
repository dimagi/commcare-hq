hqDefine('prototype.workflow_builder.utils', function () {
    'use strict';
    var module = {};
    var _private = {};

    _private.generateUUID = function() {
        var d = new Date().getTime();
        var uuid = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = (d + Math.random()*16)%16 | 0;
            d = Math.floor(d/16);
            return (c=='x' ? r : (r&0x3|0x8)).toString(16);
        });
        return uuid;
    };

    module.WorkflowType = {
        SURVEY: 'SURVEY',
        FOLLOWUP: 'FOLLOWUP',
        COMPLETE: 'COMPLETE',
    };

    module.FormType = {
        SURVEY: 'SURVEY',
        REGISTRATION: 'REGISTRATION',
        FOLLOWUP: 'FOLLOWUP',
        COMPLETION: 'COMPLETION',
    };

    module.FormContainerClass = {
        SURVEY: 'workflow-form-survey',
        REGISTRATION: 'workflow-form-registration',
        FOLLOWUP: 'workflow-form-followup',
        COMPLETION: 'workflow-form-completion',
    };

    module.FormContainerTemplate = {
        SURVEY: 'ko-template-container-survey',
        REGISTRATION: 'ko-template-container-registration',
        FOLLOWUP: 'ko-template-container-followup',
        FOLLOWUP_ONLY: 'ko-template-container-followup-only',
        COMPLETION: 'ko-template-container-completion',
    };

    module.BaseAppObj = function () {
        var self = this;
        self.uuid = ko.observable(_private.generateUUID());
        self.name = ko.observable();
        self.modalId = ko.computed(function () {
            return 'modal-settings-' + self.uuid();
        });
        self.draggableId = ko.computed(function () {
            return 'draggable_obj_' + self.uuid();
        });
    };

    return module;
});
