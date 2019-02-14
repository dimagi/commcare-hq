# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

from django.core.management.base import BaseCommand

from corehq.apps.app_manager.dbaccessors import get_current_app, get_latest_build_version
from corehq.apps.app_manager.models import (
    AdvancedForm,
    AdvancedModule,
    AdvancedOpenCaseAction,
    CaseIndex,
    Form,
    LoadUpdateAction,
)
from corehq.apps.app_manager.suite_xml.utils import get_select_chain

DUE_LIST_XMLNS = "http://openrosa.org/formdesigner/619B942A-362E-43DE-8650-ED37026D9AC4"
IMMUNIZATION_XMLNS = "http://openrosa.org/formdesigner/58C65452-D21D-4935-A746-256E7C22224D"
ELIGIBLE_COUPLE_XMLNS = "http://openrosa.org/formdesigner/21A52E12-3C84-4307-B680-1AB194FCE647"


class Command(BaseCommand):
    help = """
    Converts a basic module to an advanced module.
    """

    def add_arguments(self, parser):
        parser.add_argument('domain', type=str)
        parser.add_argument('app_id', type=str)
        parser.add_argument('module_id', type=str)

    def handle(self, domain, app_id, module_id, *args, **options):
        app = get_current_app(domain, app_id)
        module = app.get_module_by_unique_id(module_id)

        assert module.doc_type == 'Module', "Only support modules"
        assert module.display_style == 'list', "Doesn't support grid case lists"
        assert module.referral_list.show is False, "Doesn't support referral lists"
        assert module.ref_details.short.columns == [], "Doesn't support ref details"
        assert module.ref_details.long.columns == [], "Doesn't support ref details"
        assert module.task_list.show is False, "Doesn't support task lists"

        latest_build = get_latest_build_version(domain, app_id)
        if latest_build != app.version:
            app.validate_app()
            copy = app.make_build(
                comment="Build before moving {} to an advanced module".format(module.name),
            )
            copy.save(increment_version=False)

        module.module_type = 'advanced'
        module.doc_type = 'AdvancedModule'

        forms = []
        for form in module.forms:
            # https://github.com/dimagi/commcare-hq/blob/271ab9346745e7a8a4d647db66dc959fbb9f8159/corehq/apps/app_manager/models.py#L3182
            assert isinstance(form, Form)
            new_form = AdvancedForm(
                name=form.name,
                form_filter=form.form_filter,
                media_image=form.media_image,
                media_audio=form.media_audio,
                comment=form.comment,
            )
            new_form._parent = module
            form._parent = module

            new_form.source = form.source

            actions = form.active_actions()
            open = actions.get('open_case', None)
            update = actions.get('update_case', None)
            close = actions.get('close_case', None)
            preload = actions.get('case_preload', None)
            subcases = actions.get('subcases', None)
            case_type = module.case_type

            base_action = None
            if open:
                base_action = AdvancedOpenCaseAction(
                    case_type=case_type,
                    case_tag='open_{0}_0'.format(case_type),
                    name_path=open.name_path,
                    open_condition=open.condition,
                    case_properties=update.update if update else {},
                )
                new_form.actions.open_cases.append(base_action)
            elif update or preload or close:
                base_action = LoadUpdateAction(
                    case_type=case_type,
                    case_tag='load_{0}_0'.format(case_type),
                    case_properties=update.update if update else {},
                    preload=preload.preload if preload else {},
                )

                if module.parent_select.active:
                    select_chain = get_select_chain(app, module, include_self=False)
                    for n, link in enumerate(reversed(list(enumerate(select_chain)))):
                        i, module = link
                        new_form.actions.load_update_cases.append(LoadUpdateAction(
                            case_type=module.case_type,
                            case_tag='_'.join(['parent'] * (i + 1)),
                            details_module=module.unique_id,
                            case_index=CaseIndex(tag='_'.join(['parent'] * (i + 2)) if n > 0 else ''),
                        ))

                    base_action.case_indices = [CaseIndex(tag='parent')]

                if close:
                    base_action.close_condition = close.condition
                new_form.actions.load_update_cases.append(base_action)

            if subcases:
                for i, subcase in enumerate(subcases):
                    open_subcase_action = AdvancedOpenCaseAction(
                        case_type=subcase.case_type,
                        case_tag='open_{0}_{1}'.format(subcase.case_type, i + 1),
                        name_path=subcase.case_name,
                        open_condition=subcase.condition,
                        case_properties=subcase.case_properties,
                        repeat_context=subcase.repeat_context,
                        case_indices=[CaseIndex(
                            tag=base_action.case_tag if base_action else '',
                            reference_id=subcase.reference_id,
                        )],
                    )
                    new_form.actions.open_cases.append(open_subcase_action)

            new_form.unique_id = form.unique_id
            forms.append(new_form.to_json())

        new_module = module.to_json()
        new_module['forms'] = forms
        del new_module['display_style']
        del new_module['referral_list']
        del new_module['ref_details']
        del new_module['task_list']
        del new_module['parent_select']  # This is handled in forms for advanced modules

        new_module = AdvancedModule.wrap(new_module)
        modules = app.modules
        mod_index = [i for i, mod in enumerate(modules) if mod.unique_id == module_id][0]
        modules[mod_index] = new_module
        app.modules = modules
        app.save()

        # update xml
        app = get_current_app(domain, app_id)
        module = app.get_module_by_unique_id(module_id)
        for form in module.forms:
            real_form = app.get_form(form.unique_id)
            if form.xmlns in (DUE_LIST_XMLNS, IMMUNIZATION_XMLNS):
                new_form_source = form.source.replace(
                    "instance('commcaresession')/session/data/case_id",
                    "instance('commcaresession')/session/data/case_id_load_tasks_0")
                real_form.source = new_form_source
            elif form.xmlns == ELIGIBLE_COUPLE_XMLNS:
                new_form_source = form.source.replace(
                    "instance('commcaresession')/session/data/case_id",
                    "instance('commcaresession')/session/data/case_id_load_person_0")
                real_form.source = new_form_source
        app.save()
        copy = app.make_build(
            comment="{} moved to an advanced module".format(module.name),
        )
        copy.save(increment_version=False)
