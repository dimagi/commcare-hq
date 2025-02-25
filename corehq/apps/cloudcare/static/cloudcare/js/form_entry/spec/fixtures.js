import _ from "underscore";

export function textJSON(options = {}) {
    return _.defaults(options, {
        "caption_audio": null,
        "caption_video": null,
        "caption_image": null,
        "caption_markdown": null,
        "caption": "name",
        "binding": "/data/name",
        "question_id": "name",
        "required": 0,
        "relevant": 0,
        "answer": null,
        "datatype": "str",
        "style": null,
        "type": "question",
        "ix": "0",
        "choices": null,
        "repeatable": null,
        "exists": null,
        "header": null,
        "control": 1,
        "help": null,
        "help_image": null,
        "help_audio": null,
        "help_video": null,
        "hint": null,
        "output": null,
        "add-choice": null,
    });
}

export function selectJSON(options = {}) {
    return _.defaults(options, {
        "caption_audio": null,
        "caption_video": null,
        "caption_image": null,
        "caption_markdown": null,
        "caption": "choice",
        "binding": "/data/select",
        "question_id": "select",
        "required": 0,
        "relevant": 0,
        "answer": null,
        "datatype": "select",
        "style": null,
        "type": "question",
        "ix": "2",
        "choices": ["a", "b"],
        "repeatable": null,
        "exists": null,
        "header": null,
        "control": 2,
        "help": null,
        "help_image": null,
        "help_audio": null,
        "help_video": null,
        "hint": null,
        "output": null,
        "add-choice": null,
    });
}

export function labelJSON(options = {}) {
    return _.defaults(options, {
        "caption_audio": null,
        "caption_video": null,
        "caption_image": null,
        "caption_markdown": null,
        "caption": "Label",
        "binding": "/data/label",
        "question_id": "label",
        "required": 0,
        "relevant": 0,
        "answer": null,
        "datatype": "info",
        "style": {"raw": "minimal"},
        "type": "question",
        "ix": "3",
        "choices": null,
        "repeatable": null,
        "exists": null,
        "header": null,
        "control": 9,
        "help": null,
        "help_image": null,
        "help_audio": null,
        "help_video": null,
        "hint": null,
        "output": null,
        "add-choice": null,
    });
}

export function groupJSON(options = {}) {
    return _.defaults(options, {
        "type": "sub-group",
        "ix": "1",
        "exists": true,
        "caption": "Group",
        "children": [
            {
                "type": "sub-group",
                "exists": true,
                "ix": "1,2",
                "caption": "Sub Group",
                "children": [
                    {
                        "type": "question",
                        "ix": "2,3",
                        "datatype": "str",
                        "answer": null,
                        "children": [],
                    },
                    {
                        "type": "question",
                        "ix": "2,4",
                        "datatype": "str",
                        "answer": null,
                        "children": [],
                    },
                ],
            },
        ],
    });
}
export function noQuestionGroupJSON() {
    return {
        "type": "sub-group",
        "ix": "2",
        "exists": true,
        "children": [
            {
                "type": "sub-group",
                "ix": "2,2",
                "exists": true,
                "children": [],
            },
        ],
    };
}
