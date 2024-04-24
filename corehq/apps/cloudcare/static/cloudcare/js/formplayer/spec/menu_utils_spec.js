'use strict';
/* eslint-env mocha */
hqDefine("cloudcare/js/formplayer/spec/menu_utils_spec", function () {
    describe('Menu Utils', function () {

        describe('groupDisplays', function () {
            const view = hqImport("cloudcare/js/formplayer/menus/views/query");

            it('should return the displays grouped by their groupKey', function () {
                const displays = [
                    {
                        "text": "Facility Name",
                        "groupKey": "facility",
                    },
                    {
                        "text": "Facility Address",
                        "groupKey": "facility",
                    },
                    {
                        "text": "Unit Name",
                        "groupKey": "unit",
                    },
                    {
                        "text": "Floor",
                        "groupKey": "unit",
                    },
                    {
                        "text": "Capacity",
                        "groupKey": "unnamed",
                    },
                ];
                const groupHeaders =  {
                    "unit": "Unit",
                    "facility": "Facility",
                    "unnamed": "",
                };
                const grouped = view.groupDisplays(displays, groupHeaders);
                const expected = [
                    {
                        "groupKey": "facility",
                        "groupName": "Facility",
                        "displays": [
                            {
                                "text": "Facility Name",
                                "groupKey": "facility",
                            },
                            {
                                "text": "Facility Address",
                                "groupKey": "facility",
                            },
                        ],
                    },
                    {
                        "groupKey": "unit",
                        "groupName": "Unit",
                        "displays": [
                            {
                                "text": "Unit Name",
                                "groupKey": "unit",
                            },
                            {
                                "text": "Floor",
                                "groupKey": "unit",
                            },
                        ],
                    },
                    {
                        "groupKey": "unnamed",
                        "groupName": "",
                        "displays": [
                            {
                                "text": "Capacity",
                                "groupKey": "unnamed",
                            },
                        ],
                    },
                ];
                assert.deepEqual(JSON.stringify(expected), JSON.stringify(grouped));
            });

        });
    });
});
