hqDefine("cloudcare/js/formplayer/spec/fixtures/form_tree", function () {
    let questionDefaults = {
        type: "question",
        required: 0,
        relevant: 0,
        datatype: "str",
    };
    return {
        "notification": {
            "message": null,
            "error": false,
        },
        "title": "Question #Types",
        "clearSession": false,
        "appId": null,
        "appVersion": null,
        "tree": [
            _.extend(questionDefaults, {
                "caption": "The following questions will go over basic question types allowed in a form.",
                "binding": "/data/intro",
                "datatype": "info",
                "ix": "0",
            }),
            _.extend(questionDefaults, {
                "caption": "This question should let you enter any form of text or special characters. Try different values.",
                "binding": "/data/q_text",
                "ix": "1",
            }),
            _.extend(questionDefaults, {
                "caption": "This question should only let you enter an integer. [",
                "binding": "/data/q_int",
                "datatype": "int",
                "ix": "2",
            }),
            _.extend(questionDefaults, {
                "caption": "This question should only let you enter a decimal number. If you enter a whole number, proceed to the next question and then back to this one to make sure it was saved as a decimal number.",
                "binding": "/data/q_numeric",
                "datatype": "float",
                "ix": "3",
            }),
            _.extend(questionDefaults, {
                "caption": "This question should only allow you to enter a date.",
                "binding": "/data/q_date",
                "datatype": "date",
                "ix": "4",
            }),
            _.extend(questionDefaults, {
                "caption": "This question should allow you to enter a date and a time.",
                "binding": "/data/q_date_time",
                "datatype": "datetime",
                "ix": "5",
            }),
            _.extend(questionDefaults, {
                "caption": "You should be able to choose one or more answers here.",
                "binding": "/data/q_multiselect",
                "datatype": "multiselect",
                "ix": "6",
                "choices": [
                    "One",
                    "Two",
                    "Three",
                ],
            }),
            _.extend(questionDefaults, {
                "caption": "You should be able to choose only one answer here.",
                "binding": "/data/q_singleselect",
                "datatype": "select",
                "ix": "7",
                "choices": [
                    "One",
                    "Two",
                    "Three",
                ],
            }),
            _.extend(questionDefaults, {
                "caption": "This question should display with a label at the top and allow you to choose from either option on each row",
                "style": {},
                "type": "sub-group",
                "ix": "8",
                "repeatable": "false",
                "children": [
                    _.extend(questionDefaults, {
                        "caption": "Choose for each:",
                        "binding": "/data/list_view/list_label",
                        "datatype": "select",
                        "style": {
                            "raw": "label",
                        },
                        "ix": "8,0",
                        "choices": [
                            "Yes",
                            "No",
                        ],
                    }),
                    _.extend(questionDefaults, {
                        "caption": "Red",
                        "binding": "/data/list_view/red",
                        "datatype": "select",
                        "style": {
                            "raw": "list-nolabel",
                        },
                        "caption_markdown": "Red",
                        "ix": "8,1",
                        "choices": [
                            "Yes",
                            "No",
                        ],
                    }),
                    _.extend(questionDefaults, {
                        "caption": "Green",
                        "binding": "/data/list_view/Green",
                        "datatype": "select",
                        "style": {
                            "raw": "list-nolabel",
                        },
                        "type": "question",
                        "caption_markdown": "Green",
                        "ix": "8,2",
                        "choices": [
                            "Yes",
                            "No",
                        ],
                    }),
                    _.extend(questionDefaults, {
                        "caption": "Yellow",
                        "binding": "/data/list_view/Yellow",
                        "datatype": "select",
                        "style": {
                            "raw": "list-nolabel",
                        },
                        "ix": "8,3",
                        "choices": [
                            "Yes",
                            "No",
                        ],
                    }),
                ],
            }),
            _.extend(questionDefaults, {
                "caption": "This question should only allow you to enter a time.",
                "binding": "/data/q_time",
                "datatype": "time",
                "ix": "9",
            }),
            _.extend(questionDefaults, {
                "caption": "The value of this question should be hidden, but anything can be entered.",
                "binding": "/data/q_pass",
                "ix": "10",
            }),
            _.extend(questionDefaults, {
                "caption": "The value of this question should be hidden and only numbers are allowed.",
                "binding": "/data/q_pass_int",
                "ix": "11",
            }),
            _.extend(questionDefaults, {
                "caption": "You should be able to enter digits here. Enter multiple zeroes and navigate back and forth to make sure they remain.",
                "binding": "/data/numerictext",
                "style": {
                    "raw": "numeric",
                },
                "ix": "12",
            }),
            _.extend(questionDefaults, {
                "caption": "You should only see this message. It should have no confirmation box.",
                "binding": "/data/no_confirmation",
                "datatype": "info",
                "style": {
                    "raw": "minimal",
                },
                "ix": "13",
            }),
            _.extend(questionDefaults, {
                "caption": "You should be able to see this message and a confirmation box. The next set of questions will go over complex question types and will only be available on some devices.",
                "binding": "/data/q_label",
                "datatype": "info",
                "ix": "14",
            }),
            _.extend(questionDefaults, {
                "caption": "If using an Android device, you should be able to capture a signature. Try it out!",
                "binding": "/data/sig_cap",
                "datatype": "binary",
                "style": {
                    "raw": "signature",
                },
                "ix": "15",
            }),
            _.extend(questionDefaults, {
                "caption": "If using an Android device, this question should allow you to scan a barcode.",
                "binding": "/data/q_barcode",
                "datatype": "barcode",
                "ix": "16",
            }),
            _.extend(questionDefaults, {
                "caption": "If using an Android device, this question should display a QR Code (similar to a barcode. If you scanned one in the previous question, it should contain its contents.)",
                "binding": "/data/qroutput",
                "datatype": "info",
                "ix": "17",
            }),
            _.extend(questionDefaults, {
                "caption": "If using an Android device, this question should allow you to capture a GPS location. Try it out.",
                "binding": "/data/q_gps",
                "datatype": "geo",
                "ix": "18",
            }),
            _.extend(questionDefaults, {
                "caption": "If available on your device, this question should allow you to take a picture or upload an image.",
                "binding": "/data/q_image",
                "datatype": "binary",
                "ix": "19",
            }),
            _.extend(questionDefaults, {
                "caption": "If available on your device, this question should allow you to record or upload audio, and then play it.",
                "binding": "/data/q_audio",
                "datatype": "binary",
                "ix": "20",
            }),
            _.extend(questionDefaults, {
                "caption": "If available on your device, this question should allow you to record or upload video, and then play it.",
                "binding": "/data/q_video",
                "datatype": "binary",
                "ix": "21",
            }),
            _.extend(questionDefaults, {
                "caption": "If available on your device, this question should only allow you to take a picture.",
                "binding": "/data/q_image_acquire",
                "datatype": "binary",
                "style": {
                    "raw": "acquire",
                },
                "ix": "22",
            }),
            _.extend(questionDefaults, {
                "caption": "If available on your device, this question should only allow you to record audio, and then play it.",
                "binding": "/data/q_audio_acquire",
                "datatype": "binary",
                "style": {
                    "raw": "acquire",
                },
                "ix": "23",
            }),
            _.extend(questionDefaults, {
                "caption": "If available on your device, this question should only allow you to record a video, and then play it.",
                "binding": "/data/q_video_acquire",
                "datatype": "binary",
                "style": {
                    "raw": "acquire",
                },
                "ix": "24",
            }),
            _.extend(questionDefaults, {
                "caption": "Group List Question",
                "style": {},
                "type": "sub-group",
                "ix": "25",
                "repeatable": "false",
                "children": [
                    _.extend(questionDefaults, {
                        "caption": "This question should let you enter any form of text or special characters. Try different values.",
                        "binding": "/data/group_list/q_text_2",
                        "ix": "25,0",
                    }),
                    _.extend(questionDefaults, {
                        "caption": "You should be able to choose one or more answers here.",
                        "binding": "/data/group_list/q_multiselect_2",
                        "datatype": "multiselect",
                        "ix": "25,1",
                        "choices": [
                            "One",
                            "Two",
                            "Three",
                        ],
                    }),
                    _.extend(questionDefaults, {
                        "caption": "You should be able to choose only one answer here.",
                        "binding": "/data/group_list/q_singleselect_2",
                        "datatype": "select",
                        "ix": "25,2",
                        "choices": [
                            "One",
                            "Two",
                            "Three",
                        ],
                    }),
                ],
            }),
        ],
        "langs": [
            "en",
            "hin",
        ],
        "session_id": "7fad68e5-1836-494c-be04-cc1f7b8bba44",
        "seq_id": 0,
    };
});
