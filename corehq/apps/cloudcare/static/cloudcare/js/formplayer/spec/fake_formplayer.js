/**
 * Generates mock formplayer responses. Use as a fake for queryFormplayer.
 *
 * This does not support many of the options that can be passed to the real queryFormplayer.
 * It primarily fakes the selections logic.
 *
 * This contains one app, which has the following structure:
 *      m0: a menu that does not use cases
 *          m0-f0
 *      m1: a menu that uses cases
 *          m1-f0: a form that updates a case
 *  No menus use display-only forms.
 */
hqDefine("cloudcare/js/formplayer/spec/fake_formplayer", function () {
    var Util = hqImport("cloudcare/js/formplayer/spec/fixtures/util"),
        module = {},
        apps = {
            'abc123': {
                title: "My App",
                commands: [
                    {
                        title: "Survey Menu",
                        commands: [{
                            title: "Survey Form",
                        }],
                    },
                    {
                        title: "Some Cases",
                        commands: [{
                            title: "Followup Form",
                        }],
                        entities: [{
                            id: 'some_case_id',
                        }],
                    },
                ],
            },
        };

    var navigateMenuStart = function (app) {
        return Util.makeCommandResponse({
            title: app.title,
            breadcrumbs: [app.title],
            commands: app.commands,
        });
    };

    var navigateMenu = function (app, options) {
        var currentMenu = app,
            selections = options.selections,
            breadcrumbs = [app.title],
            needEntity = false;

        if (!selections || !selections.length) {
            throw new Error("No selections given to navigate_menu");
        }

        _.each(selections, function (selection) {
            if (currentMenu.commands[selection]) {
                currentMenu = currentMenu.commands[selection];
                needEntity = !!currentMenu.entities;
                breadcrumbs.push(currentMenu.title);
            } else if (_.findWhere(currentMenu.entities, {id: selection})) {
                needEntity = false;
            } else {
                throw new Error("Could not select " + selection);
            }
        });

        var responseOptions = {
            title: currentMenu.title,
            breadcrumbs: breadcrumbs,
        };
        if (needEntity) {
            return Util.makeEntityResponse(_.extend(responseOptions, {
                entities: currentMenu.entities,
            }));
        }
        return Util.makeCommandResponse(_.extend(responseOptions, {
            commands: currentMenu.commands,
        }));
    };

    module.queryFormplayer = function (options, route) {
        var app = apps[options.appId];
        if (!app) {
            throw new Error("Could not find app " + options.appId);
        }

        switch (route) {
            case "navigate_menu_start":
                return navigateMenuStart(app);
            case "navigate_menu":
                return navigateMenu(app, options);
            default:
                throw new Error("Did not recognize route " + route);
        }
        return {success: 1};
    };

    return module;
});
