'use strict';
hqDefine("cloudcare/js/formplayer/spec/fixtures/case_grid_list", [
    "cloudcare/js/formplayer/spec/fake_formplayer",
], function (
    FakeFormplayer
) {
    return FakeFormplayer.makeEntitiesResponse({
        "title": "New Adherence Data",
        "breadcrumbs": [
            "UATBC Calendar Testing",
            "[hidden] Adherence Reg Form Shell",
            "[hidden] Adherence Reg Form Shell",
            "New Adherence Data",
        ],
        "entities": [
            {
                "id": "16957",
                "data": [
                    "5",
                    "",
                    "jr://file/commcare/image/data/question1.png",
                ],
                "details": null,
            },
            {
                "id": "16958",
                "data": [
                    "6",
                    "",
                    "jr://file/commcare/image/data/question1.png",
                ],
                "details": null,
            },
            {
                "id": "17053",
                "data": [
                    "9",
                    "",
                    "jr://file/commcare/image/data/question1.png",
                ],
                "details": null,
            },
        ],
        "action": null,
        "styles": [
            {
                "fontSize": 12,
                "widthHint": null,
                "displayFormat": null,
            },
            {
                "fontSize": 12,
                "widthHint": null,
                "displayFormat": null,
            },
            {
                "fontSize": 0,
                "widthHint": null,
                "displayFormat": "Image",
            },
        ],
        "headers": [
            "Date",
            "",
            "",
        ],
        "tiles": [
            {
                "gridX": 9,
                "gridY": 0,
                "gridWidth": 3,
                "gridHeight": 2,
                "cssId": null,
                "fontSize": "medium",
            },
            {
                "gridX": 1,
                "gridY": 0,
                "gridWidth": 4,
                "gridHeight": 2,
                "cssId": null,
                "fontSize": "medium",
            },
            {
                "gridX": 0,
                "gridY": 4,
                "gridWidth": 7,
                "gridHeight": 7,
                "cssId": null,
                "fontSize": null,
            },
        ],
        "widthHints": [
            33,
            33,
            33,
        ],
        "numEntitiesPerRow": 7,
        "usesCaseTiles": true,
    });
});
