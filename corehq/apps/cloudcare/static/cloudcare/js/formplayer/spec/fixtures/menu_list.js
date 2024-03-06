'use strict';
hqDefine("cloudcare/js/formplayer/spec/fixtures/menu_list", function () {
    let FakeFormplayer = hqImport("cloudcare/js/formplayer/spec/fake_formplayer");

    return FakeFormplayer.makeCommandsResponse({
        "title": "Case Tests",
        "breadcrumbs": [
            "Basic",
            "Case Tests",
        ],
        "commands": [
            {
                "index": 0,
                "displayText": "Create a Case",
                "navigationState": "JUMP",
            },
            {
                "index": 1,
                "displayText": "Update a Case",
                "navigationState": "NEXT",
            },
            {
                "index": 2,
                "displayText": "Close a Case",
                "navigationState": "NEXT",
            },
            {
                "index": 3,
                "displayText": "Create a Sub Case",
                "navigationState": "NEXT",
            },
            {
                "index": 4,
                "displayText": "Create Multiple Sub Cases",
                "navigationState": "NEXT",
            },
            {
                "index": 5,
                "displayText": "Case list",
                "navigationState": "NEXT",
            },
        ],
        "type": "commands",
    });
});
