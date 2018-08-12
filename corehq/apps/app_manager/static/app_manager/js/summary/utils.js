hqDefine("app_manager/js/summary/utils", function() {
    var translateName = function(names, targetLang, langs) {
        var langs = [targetLang].concat(langs),
            firstLang = _(langs).find(function(lang) {
                return names[lang];
            });
        if (!firstLang) {
            return gettext('[unknown]');;
        }
        return names[firstLang] + (firstLang === targetLang ? '' : ' [' + firstLang + ']');
    };

    var formIcon = function(form) {
        var formIcon = 'fa fa-file-o appnav-primary-icon';
        if (form.action_type === 'open') {
            formIcon = 'fcc fcc-app-createform appnav-primary-icon appnav-primary-icon-lg';
        } else if (form.action_type === 'close') {
            formIcon = 'fcc fcc-app-completeform appnav-primary-icon appnav-primary-icon-lg';
        } else if (form.action_type === 'update') {
            formIcon = 'fcc fcc-app-updateform appnav-primary-icon appnav-primary-icon-lg';
        }
        return formIcon;
    };

    var moduleIcon = function(module) {
        var moduleIcon = 'fa fa-folder-open appnav-primary-icon';
        if (module.module_type === 'advanced') {
            moduleIcon = 'fa fa-flask appnav-primary-icon';
        } else if (module.module_type === 'report') {
            moduleIcon = 'fa fa-bar-chart appnav-primary-icon';
        } else if (module.module_type === 'shadow') {
            moduleIcon = 'fa fa-folder-open-o appnav-primary-icon';
        } else if (!module.is_surveys) {
            moduleIcon = 'fa fa-bars appnav-primary-icon';
        }
        return moduleIcon;
    };

    var questionModel = function(question) {    // TODO: move? this isn't a util. could make it a util, though.
        var self = _.extend({
            options: [],
        }, question);

        var vellumType = hqImport("hqwebapp/js/initial_page_data").get('VELLUM_TYPES')[question.type];
        self.icon = 'hq-icon ' + (vellumType ? vellumType.icon : '');

        self.isVisible = ko.observable(true);

        return self;
    };


    return {
        formIcon: formIcon,
        moduleIcon: moduleIcon,
        questionModel: questionModel,
        translateName: translateName,
    };
});
