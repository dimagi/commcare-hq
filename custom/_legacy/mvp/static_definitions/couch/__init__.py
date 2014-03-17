"""
    The format for defining the indicators:
    Ideally there'd be a UI for this, but there isn't.

    INDICATOR_DEFS = dict(
        app="<mvp_app name>",
        indicators=dict(
            <couch_view in mvp_app>=dict(
                <indicator_slug>=dict(
                    **init_kwargs
                )
            )
        )
    )

"""
