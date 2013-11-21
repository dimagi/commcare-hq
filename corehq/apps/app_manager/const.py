APP_V1 = '1.0'
APP_V2 = '2.0'

CAREPLAN_GOAL = 'careplan_goal'
CAREPLAN_TASK = 'careplan_task'
CAREPLAN_CASE_NAMES = {
    CAREPLAN_GOAL: 'Goal',
    CAREPLAN_TASK: 'Task'
}

CAREPLAN_DEFAULT_CASE_PROPERTIES = {
    CAREPLAN_GOAL: {
        'create': {
            'description': '/data/description',
            'date_followup': '/data/date_followup',
        },
        'update': {
            'description': '/data/description_group/description',
            'date_followup': '/data/date_followup',
        },
    },
    CAREPLAN_TASK: {
        'create': {
            'description': '../../../description',
            'date_followup': '../../../description',
        },
        'update': {
            'description': '/data/description',
            'date_followup': '/data/date_followup',
            'latest_report': '/data/progress_group/progress_update'
        }
    },
}

CAREPLAN_NAME_PATH = '/data/name'