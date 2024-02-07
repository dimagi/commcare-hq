hqDefine("export/spec/data/export_instances", [], function () {
    return {
        basic: {
            "name": null,
            "type": "form",
            "domain": "domain",
            "app_id": "1234",
            "tables": [{
                "path": null,
                "name": null,
                "selected": true,
                "columns": [{
                    "show": true,
                    "item": {
                        "path": ["data", "question1"],
                        "doc_type": "ScalarItem",
                        "last_occurrences": {
                            "e44df667860aa2bd2f9a2782511384c3": 64,
                        },
                        "tag": null,
                        "label": "question1",
                    },
                    "selected": false,
                    "label": "question1",
                    "doc_type": "ExportColumn",
                    "tags": [],
                }, {
                    "show": true,
                    "item": {
                        "doc_type": "MultipleChoiceItem",
                        "last_occurrences": {
                            "e44df667860aa2bd2f9a2782511384c3": 64,
                        },
                        "label": "question3",
                        "tag": null,
                        "path": ["data", "question3"],
                        "options": [{
                            "doc_type": "Option",
                            "last_occurrences": {
                                "e44df667860aa2bd2f9a2782511384c3": 64,
                            },
                            "value": "choice1",
                        }, {
                            "doc_type": "Option",
                            "last_occurrences": {
                                "e44df667860aa2bd2f9a2782511384c3": 64,
                            },
                            "value": "choice2",
                        }],
                    },
                    "selected": false,
                    "label": "question3",
                    "doc_type": "ExportColumn",
                    "tags": [],
                }],
                "doc_type": "TableConfiguration",
            }],
            "export_format": "csv",
            "doc_type": "ExportInstance",
            "is_deidentified": false,
        },
        saved: {
            "_id": "1234",
            "name": null,
            "type": "form",
            "tables": [{
                "selected": true,
                "path": null,
                "name": null,
                "columns": [{
                    "show": true,
                    "item": {
                        "path": ["data", "question1"],
                        "doc_type": "ScalarItem",
                        "last_occurrences": {
                            "e44df667860aa2bd2f9a2782511384c3": 64,
                        },
                        "tag": null,
                        "label": "question1",
                    },
                    "selected": false,
                    "label": "question1",
                    "doc_type": "ExportColumn",
                    "tags": [],
                }, {
                    "show": true,
                    "item": {
                        "doc_type": "MultipleChoiceItem",
                        "last_occurrences": {
                            "e44df667860aa2bd2f9a2782511384c3": 64,
                        },
                        "label": "question3",
                        "tag": null,
                        "path": ["data", "question3"],
                        "options": [{
                            "doc_type": "Option",
                            "last_occurrences": {
                                "e44df667860aa2bd2f9a2782511384c3": 64,
                            },
                            "value": "choice1",
                        }, {
                            "doc_type": "Option",
                            "last_occurrences": {
                                "e44df667860aa2bd2f9a2782511384c3": 64,
                            },
                            "value": "choice2",
                        }],
                    },
                    "selected": false,
                    "label": "question3",
                    "doc_type": "ExportColumn",
                    "tags": [],
                }],
                "doc_type": "TableConfiguration",
            }],
            "export_format": "csv",
            "doc_type": "ExportInstance",
            "is_deidentified": false,
        },
    };
});
