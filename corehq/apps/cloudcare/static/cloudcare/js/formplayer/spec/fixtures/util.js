hqDefine("cloudcare/js/formplayer/spec/fixtures/util", function () {
    var AssertProperties = hqImport("hqwebapp/js/assert_properties"),
        module = {};

    module.makeResponse = function (options) {
        AssertProperties.assertRequired(["title", "breadcrumbs"]);
        return _.defaults(options, {
            "notification": {"message": null, "error": false},
            "clearSession": false,
            "appId": "5319fe096062b0e282bf37e6faa81566",
            "appVersion": "CommCare Version: 2.27, App Version: 93",
            "locales": ["default", "en", "hin"],
            "menuSessionId": "e9fad761-5239-4096-bb71-0aba1ebd7377",
        });
    };

    module.makeCommandResponse = function (options) {
        AssertProperties.assertRequired(["commands"]);
        return _.defaults(module.makeResponse(options), {
            type: "commands",
        });
    };

    module.makeEntityResponse = function (options) {
        AssertProperties.assertRequired(["entities"]);
        return _.defaults(module.makeResponse(options), {
            "numEntitiesPerRow": 0,
            "pageCount": 2,
            "currentPage": 0,
            "type": "entities",
            "usesCaseTiles": false,
            "maxWidth": 0,
            "maxHeight": 0,
        });
    };

    module.makeQueryResponse = function (options) {
        AssertProperties.assertRequired(["displays", "queryKey"]);
        return _.defaults(module.makeResponse(options), {
            type: "query",
        });
    };

    return module;
});
