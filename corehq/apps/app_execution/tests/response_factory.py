import uuid


def command_response(selections, commands):
    return {
        'title': 'Simple app',
        'selections': selections,
        'commands': [{'index': index, 'displayText': command} for index, command in enumerate(commands)],
        'type': 'commands',
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
        'title': 'Followup Form',
        'selections': selections,
        'entities': entities,
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
        'title': 'Survey',
        'selections': selections,
        'tree': questions,
        'session_id': '8e212c16-00ac-4060-bcee-a42ad430f614'
    }


def make_entities(names):
    return [make_entity(name) for name in names]


def make_entity(name):
    return {'id': str(uuid.uuid4()), 'data': [name]}


def make_questions(captions, datatype='str'):
    return [
        make_question(ix, caption, f'question_{ix}', datatype=datatype)
        for ix, caption in enumerate(captions)
    ]


def make_question(ix, caption, question_id, answer=None, datatype='str', type_='question', choices=None):
    return {
        'ix': ix,
        'caption': caption,
        'question_id': question_id,
        'answer': answer,
        'datatype': datatype,
        'type': type_,
        'choices': choices,
    }
