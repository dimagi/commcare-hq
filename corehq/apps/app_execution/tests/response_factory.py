import uuid


def command_response(selections, commands):
    return {
        "title": "Simple app",
        "selections": selections,
        "commands": [{"index": index, "displayText": command} for index, command in enumerate(commands)],
        "type": "commands",
    }


def entity_list_response(selections, entities):
    """
    Returns a response for a form screen

    Args:
        selections: list of selections
        entities: list of entities
            id: str
            data: list[str]
    """
    return {
        "title": "Followup Form",
        "type": "entities",
        "selections": selections,
        "entities": entities,
    }


def query_response(selections, query_key, displays):
    """
    Returns a response for a search screen

    Args:
        selections: list of selections
        query_key: query key
        displays: list of displays
            id: str
            value: str
            required: bool
            allow_blank_value: bool
    """
    return {
        "title": "Case Search",
        "type": "query",
        "queryKey": query_key,
        "selections": selections,
        "displays": displays,
    }


def form_response(selections, questions):
    """
    Returns a response for a form screen

    Args:
        selections: list of selections
        questions: list of questions
            ix: str
            caption: str
            question_id: str
            answer: str | None
            datatype: str
            type: str
            choices: list[str] | None
    """
    return {
        "title": "Survey",
        "selections": selections,
        "tree": questions,
        "session_id": "8e212c16-00ac-4060-bcee-a42ad430f614"
    }


def make_entities(case_data):
    return [make_entity(case) for case in case_data]


def make_entity(case):
    return {"id": case.get("id", str(uuid.uuid4())), "data": [case["name"]]}


def make_questions(captions, datatype="str"):
    return [
        make_question(ix, caption, f"question_{ix}", datatype=datatype)
        for ix, caption in enumerate(captions)
    ]


def make_question(ix, caption, question_id, answer=None, datatype="str", type_="question", choices=None):
    return {
        "ix": ix,
        "caption": caption,
        "question_id": question_id,
        "answer": answer,
        "datatype": datatype,
        "type": type_,
        "choices": choices,
    }
