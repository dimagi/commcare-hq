/* globals hqDefine, ko, _ */
hqDefine('app_manager/js/shadow-module-settings.js', function () {
    var module = {

        /**
         * Returns a Knockout view model based on the modules and forms given in modules
         */
        ShadowModule: function (modules, selectedModuleId, excludedFormIds) {
            var self = this;
            self.modules = ko.observableArray();
            self.selectedModuleId = ko.observable(selectedModuleId);
            self.selectedModule = ko.computed(function () {
                return _.findWhere(self.modules(), {uniqueId: self.selectedModuleId()});
            });

            var SourceModule = function (uniqueId, name) {
                this.uniqueId = uniqueId;
                this.name = name;
                this.forms = ko.observableArray();
                this.includedFormIds = ko.observableArray();
            };

            var SourceModuleForm = function (uniqueId, name) {
                this.uniqueId = uniqueId;
                this.name = name;
            };

            var sourceModule = new SourceModule('', 'None');
            self.modules.push(sourceModule);
            for (var i = 0; i < modules.length; i++) {
                var mod = modules[i];
                sourceModule = new SourceModule(mod.unique_id, mod.name);
                for (var j = 0; j < mod.forms.length; j++) {
                    var form = mod.forms[j];
                    var sourceModuleForm = new SourceModuleForm(form.unique_id, form.name);
                    sourceModule.forms.push(sourceModuleForm);
                    if (excludedFormIds.indexOf(form.unique_id) === -1) {
                        sourceModule.includedFormIds.push(form.unique_id);
                    }
                }
                self.modules.push(sourceModule);
            }
        },
    };
    return module;
});
