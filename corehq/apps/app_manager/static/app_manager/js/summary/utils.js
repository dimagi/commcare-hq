hqDefine("app_manager/js/summary/utils",[
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
], function ($, _, initialPageData) {
    var translateName = function (names, targetLang, allLangs) {
        var langs = [targetLang].concat(allLangs),
            firstLang = _(langs).find(function (lang) {
                return names[lang];
            });
        if (!firstLang) {
            return gettext('[unknown]');
        }
        return names[firstLang] + (firstLang === targetLang ? '' : ' [' + firstLang + ']');
    };

    var formIcon = function (form) {
        var formIcon = 'fa-regular fa-file appnav-primary-icon';
        if (form.action_type === 'open') {
            formIcon = 'fcc fcc-app-createform appnav-primary-icon appnav-primary-icon-lg';
        } else if (form.action_type === 'close') {
            formIcon = 'fcc fcc-app-completeform appnav-primary-icon appnav-primary-icon-lg';
        } else if (form.action_type === 'update') {
            formIcon = 'fcc fcc-app-updateform appnav-primary-icon appnav-primary-icon-lg';
        }
        return formIcon;
    };

    var moduleIcon = function (module) {
        var moduleIcon = 'fa fa-folder-open appnav-primary-icon';
        if (module.module_type === 'advanced') {
            moduleIcon = 'fa fa-flask appnav-primary-icon';
        } else if (module.module_type === 'report') {
            moduleIcon = 'fa-regular fa-chart-bar appnav-primary-icon';
        } else if (module.module_type === 'shadow') {
            moduleIcon = 'fa-regular fa-folder-open appnav-primary-icon';
        } else if (!module.is_surveys) {
            moduleIcon = 'fa fa-bars appnav-primary-icon';
        }
        return moduleIcon;
    };

    var questionIcon = function (question) {
        var vellumType = initialPageData.get('VELLUM_TYPES')[question.type];
        return 'hq-icon ' + (vellumType ? vellumType.icon : '');
    };

    return {
        formIcon: formIcon,
        moduleIcon: moduleIcon,
        questionIcon: questionIcon,
        translateName: translateName,
    };
});
