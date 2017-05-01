def should_show_preview_app(request, app, username):
    return not app.is_remote_app()
