/* globals hqDefine, ko, _ */
hqDefine('app_manager/js/modules/shadow_module_settings', function () {
    var module = {

        /**
         * Returns a Knockout view model based on the modules and forms given in modules
         */
        ShadowModule: function (modules, selectedModuleId, excludedFormIds) {
            var self = this;
            self.modules = ko.observableArray();
            self.selectedModuleId = ko.observable(selectedModuleId);
            self.selectedModule = ko.pureComputed(function () {
                return _.findWhere(self.modules(), {uniqueId: self.selectedModuleId()});
            });
            // Find all forms that could potentially be included in the current module:
            // Forms belonging to the source module and to the source module's children
            self.sourceForms = ko.pureComputed(function() {
                return self.selectedModule().forms().concat(_.flatten(_.map(_.filter(self.modules(), function(m) {
                    return m.rootId === self.selectedModuleId();
                }), function(m) {
                    return m.forms();
                })));
            });
            self.includedFormIds = ko.observableArray();
            self.excludedFormIds = ko.pureComputed(function () {
                var exclForms = _.filter(self.sourceForms(), function (form) {
                    return self.includedFormIds().indexOf(form.uniqueId) === -1;
                });
                return _.map(exclForms, function (form) { return form.uniqueId; });
            });

            var SourceModule = function (uniqueId, name, rootId) {
                this.uniqueId = uniqueId;
                this.name = name;
                this.rootId = rootId;
                this.forms = ko.observableArray();
            };

            var SourceModuleForm = function (uniqueId, name) {
                this.uniqueId = uniqueId;
                this.name = name;
            };

            var sourceModule = new SourceModule('', 'None');
            self.modules.push(sourceModule);
            for (var i = 0; i < modules.length; i++) {
                var mod = modules[i];
                sourceModule = new SourceModule(mod.unique_id, mod.name, mod.root_module_id);
                for (var j = 0; j < mod.forms.length; j++) {
                    var form = mod.forms[j];
                    var sourceModuleForm = new SourceModuleForm(form.unique_id, form.name);
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
