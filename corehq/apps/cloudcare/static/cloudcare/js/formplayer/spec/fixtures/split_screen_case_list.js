'use strict';
hqDefine("cloudcare/js/formplayer/spec/fixtures/split_screen_case_list", [
    "cloudcare/js/formplayer/spec/fake_formplayer",
], function (
    FakeFormplayer
) {
    return FakeFormplayer.makeEntitiesResponse({
        "title": "Search All Cases",
        "description": "",
        "actions": [
            null,
        ],
        "breadcrumbs": [
            "Basic",
            "Case Tests",
            "Update a Case",
        ],
        "entities": [
            {
                "id": "8ee76803-dcfc-4f90-b005-b8a810212072",
                "data": [
                    "Moose",
                    "male",
                    "1990-12-24",
                    "Jack Russell Terrier",
                ],
                "details": null,
            },
            {
                "id": "554e91bf-355a-489f-9f09-f3b5af02b04e",
                "data": [
                    "Kimchi",
                    "female",
                    "2022-06-01",
                    "Shih Tzu",
                ],
                "details": null,
            },
        ],
        "groupHeaders": {
            "groupKey": "group name",
        },
        "headers": [
            "Name",
            "Sex",
            "DOB",
            "Breed",
        ],
        "multiSelect": false,
        "queryKey": "search_command.m0",
        "queryResponse": {
            "title": "Search All Cases",
            "description": "",
            "displays": [
                {
                    "text": "Name",
                    "id": "case_name",
                    "hint": "Enter a name",
                    "required": true,
                    "required_msg": "This field is required",
                    "groupKey": "groupKey",
                },
            ],
            "queryKey": "search_command.m0",
            "type": "query",
            "groupHeaders": {
                "groupKey": "group name",
            },
        },
        "styles": [
            {
                "fontSize": 0,
                "widthHint": -1,
                "displayFormat": null,
            },
            {
                "fontSize": 0,
                "widthHint": -1,
                "displayFormat": null,
            },
        ],
        "tiles": null,
        "widthHints": [
            20,
            20,
            20,
            20,
        ],
    });
});
