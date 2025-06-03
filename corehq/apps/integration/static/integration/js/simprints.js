import $ from "jquery";
import ko from "knockout";


export default {
    simprintsFormModel: function (formData) {
        var self = {};

        self.isEnabled = ko.observable(formData.is_enabled);
        self.projectId = ko.observable(formData.project_id);
        self.userId = ko.observable(formData.user_id);
        self.moduleId = ko.observable(formData.module_id);

        // todo slug validation

        return self;
    },
};
