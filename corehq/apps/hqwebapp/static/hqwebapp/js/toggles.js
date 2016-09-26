hqDefine('hqwebapp/js/toggles.js', function () {
    var genericToggleEnabled = function (allToggles, toggleName) {
        var value = allToggles[toggleName];
        if (typeof value === 'undefined') {
            throw new Error(
                'Toggle ' + toggleName + 'not recognized. Must be one of: \n\n' +
                _.sortBy(_.keys(allToggles).join("\n"))
            );
        }
        return value;
    };
    return {
        toggleEnabled: function (toggleName) {
            return genericToggleEnabled(hqImport('#toggles').toggles, toggleName);
        },
        previewEnabled: function (toggleName) {
            return genericToggleEnabled(hqImport('#toggles').previews, toggleName);
        }
    };
});
