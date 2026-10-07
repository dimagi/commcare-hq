from unmagic import use

from corehq.apps.public_webforms.tests.utils import create_webform, saved_app


@use(saved_app)
def test_deleting_an_app_closes_its_public_webforms():
    app = saved_app()
    webform = create_webform(app_id=app._id, is_disabled=False)

    app.delete_app()
    app.save()

    webform.refresh_from_db()
    assert webform.is_disabled


@use(saved_app)
def test_saving_a_live_app_leaves_its_public_webforms_open():
    app = saved_app()
    webform = create_webform(app_id=app._id, is_disabled=False)

    app.save()

    webform.refresh_from_db()
    assert not webform.is_disabled
