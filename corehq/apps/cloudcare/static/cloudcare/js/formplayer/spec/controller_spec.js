/* eslint-env mocha */
/* global Backbone */
hqDefine("cloudcare/js/formplayer/spec/controller_spec", function () {
    describe('Controller', function () {

        describe('groupDisplays', function () {
            const controller = hqImport("cloudcare/js/formplayer/menus/controller");


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
	            ]
                const groupHeaders =  {
                    "unit": "Unit",
                    "facility": "Facility",
                    "unnamed": "",
                }

                const grouped = controller.groupDisplays(displays, groupHeaders);
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
                ]
                console.log(grouped);
                assert.deepEqual(expected, grouped, JSON.stringify(grouped));
            });

        });
    });
});
