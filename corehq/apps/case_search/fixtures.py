from corehq.messaging.templating import (
    MessagingTemplateRenderer,
    NestedDictTemplateParam,
)


def _get_user_template_info(restore_user):
    return {
        "username": restore_user.username,
        "uuid": restore_user.user_id,
        "user_data": restore_user.user_session_data
    }


def _get_template_renderer(restore_user):
    renderer = MessagingTemplateRenderer()
    renderer.set_context_param('user', NestedDictTemplateParam(_get_user_template_info(restore_user)))
    return renderer
