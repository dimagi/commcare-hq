from corehq.apps.app_manager.suite_xml.xml import SessionDatum


class EntriesHelper(object):
    @staticmethod
    def get_new_case_id_datums_meta(form):
        if not form:
            return []

        datums = []
        if form.form_type == 'module_form':
            actions = form.active_actions()
            if 'open_case' in actions:
                datums.append({
                    'datum': SessionDatum(id=form.session_var_for_action('open_case'), function='uuid()'),
                    'case_type': form.get_module().case_type,
                    'requires_selection': False,
                    'action': actions['open_case']
                })

            if 'subcases' in actions:
                for i, subcase in enumerate(actions['subcases']):
                    # don't put this in the loop to be consistent with the form's indexing
                    # see XForm.create_casexml_2
                    if not subcase.repeat_context:
                        datums.append({
                            'datum': SessionDatum(
                                id=form.session_var_for_action('subcases', i), function='uuid()'
                            ),
                            'case_type': subcase.case_type,
                            'requires_selection': False,
                            'action': subcase
                        })
        elif form.form_type == 'advanced_form':
            for action in form.actions.get_open_actions():
                if not action.repeat_context:
                    datums.append({
                        'datum': SessionDatum(id=action.case_session_var, function='uuid()'),
                        'case_type': action.case_type,
                        'requires_selection': False,
                        'action': action
                    })

        return datums
