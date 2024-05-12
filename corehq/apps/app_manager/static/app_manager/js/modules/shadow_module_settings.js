hqDefine('app_manager/js/modules/shadow_module_settings', function () {
    const module = {

        /**
         * Returns a Knockout view model based on the modules and forms given in modules
         */
        ShadowModule: function (modules, selectedModuleId, excludedFormIds, formSessionEndpointMappings, shadowModuleVersion) {
            const self = this;
            self.modules = ko.observableArray();
            self.shadowModuleVersion = shadowModuleVersion;
            self.selectedModuleId = ko.observable(selectedModuleId);
            self.selectedModule = ko.pureComputed(function () {
                return _.findWhere(self.modules(), {uniqueId: self.selectedModuleId()});
            });
            // Find all forms that could potentially be included in the current module:
            self.sourceForms = ko.pureComputed(function () {
                if (self.shadowModuleVersion === 1) {
                    // Forms belonging to the source module and to the source module's children
                    return self.selectedModule().forms().concat(_.flatten(_.map(_.filter(self.modules(), function (m) {
                        return m.rootId === self.selectedModuleId();
                    }), function (m) {
                        return m.forms();
                    })));
                } else {
                    // Forms belonging only to the source module
                    return self.selectedModule().forms();
                }

            });
            self.includedFormIds = ko.observableArray();
            self.excludedFormIds = ko.pureComputed(function () {
                const exclForms = _.filter(self.sourceForms(), function (form) {
                    return self.includedFormIds().indexOf(form.uniqueId) === -1;
                });
                return _.map(exclForms, function (form) { return form.uniqueId; });
            });

            self.formSessionEndpointIds = ko.pureComputed(function () {
                return _.map(self.sourceForms(), function (form) {
                    return ko.pureComputed(function () {
                        return JSON.stringify({form_id: form.uniqueId, session_endpoint_id: form.sessionEndpointId()});
                    });
                });
            });

            const sourceModuleModel = function (uniqueId, name, rootId) {
                const self = {};

                self.uniqueId = uniqueId;
                self.name = name;
                self.rootId = rootId;
                self.forms = ko.observableArray();

                return self;
            };

            const sourceModuleFormModel = function (uniqueId, name, sessionEndpointId) {
                return {
                    uniqueId: uniqueId,
                    name: name,
                    sessionEndpointId: ko.observable(sessionEndpointId),
                };
            };

            let sourceModule = sourceModuleModel('', 'None');
            self.modules.push(sourceModule);
            modules = _.sortBy(modules, function (m) { return m.name; });
            for (let i = 0; i < modules.length; i++) {
                const mod = modules[i];
                sourceModule = sourceModuleModel(mod.unique_id, mod.name, mod.root_module_id);
                for (let j = 0; j < mod.forms.length; j++) {
                    const form = mod.forms[j];
                    let formSessionEndpointId = "";
                    const mapping = _.find(formSessionEndpointMappings, m => m.form_id === form.unique_id);
                    if (mapping) {
                        formSessionEndpointId = mapping.session_endpoint_id;
                    }
                    const sourceModuleForm =
                        sourceModuleFormModel(form.unique_id, form.name, formSessionEndpointId);
                    sourceModule.forms.push(sourceModuleForm);
                    if (excludedFormIds.indexOf(form.unique_id) === -1) {
                        self.includedFormIds.push(form.unique_id);
                    }
                }
                self.modules.push(sourceModule);
            }
        },
    };
    return module;
});
