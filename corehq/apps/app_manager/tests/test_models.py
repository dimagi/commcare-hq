from django.test import SimpleTestCase
from corehq.apps.app_manager.exceptions import (
    MissingPropertyMapException,
    DiffConflictException,
    InvalidPropertyException
)
from corehq.apps.app_manager.models import (
    FormActions, UpdateCaseAction, OpenCaseAction, OpenCaseDiff, UpdateCaseDiff, FormActionsDiff
)


class UpdateableDocumentTests(SimpleTestCase):
    def test_handles_partially_specified_update(self):
        actions = FormActions()
        updates = {
            'usercase_update': {
                'update': {
                    'one': {
                        'question_path': 'test_path',
                        'update_mode': 'edit',
                    }
                },
                'condition': {
                    'type': 'always',
                    'question': 'test_question',
                    'answer': 'yes',
                    'operator': 'selected'
                }
            }
        }

        actions.update_object(updates)

        # Verify that empty values remain empty
        self.assertEqual(actions.update_case.update, {})

        # Verify that the updated values were applied
        self.assertEqual(set(actions.usercase_update.update.keys()), {'one'})
        self.assertEqual(actions.usercase_update.update['one'].question_path, 'test_path')
        self.assertEqual(actions.usercase_update.update['one'].update_mode, 'edit')

        self.assertEqual(actions.usercase_update.condition['type'], 'always')
        self.assertEqual(actions.usercase_update.condition['question'], 'test_question')
        self.assertEqual(actions.usercase_update.condition['answer'], 'yes')
        self.assertEqual(actions.usercase_update.condition['operator'], 'selected')

    def test_throws_error_on_unrecognized_key(self):
        actions = FormActions()
        updates = {
            'malicious_key': {
                'update': {}
            }
        }

        with self.assertRaises(InvalidPropertyException) as context:
            actions.update_object(updates)

        self.assertEqual(context.exception.invalid_property, 'malicious_key')


class OpenCaseActionTests(SimpleTestCase):
    def test_construction(self):
        action = OpenCaseAction({'name_update': {'question_path': 'name'}})

        self.assertEqual(action.name_update.question_path, 'name')

    def test_multiple_name_updates(self):
        action = OpenCaseAction({
            'name_update_multi': [{'question_path': 'name1'}, {'question_path': 'name2'}]
        })
        multi_paths = [update.question_path for update in action.name_update_multi]
        self.assertEqual(multi_paths, ['name1', 'name2'])

    def test_make_multi_populates_multi(self):
        action = OpenCaseAction({
            'name_update': {'question_path': 'name'}
        })

        action.make_multi()

        multi_paths = [update.question_path for update in action.name_update_multi]
        self.assertEqual(multi_paths, ['name'])
        self.assertIsNone(action.name_update)

    def test_make_multi_does_nothing_when_update_multi_already_exists(self):
        action = OpenCaseAction({
            'name_update_multi': [{'question_path': 'one'}, {'question_path': 'two'}]
        })

        action.make_multi()

        multi_paths = [update.question_path for update in action.name_update_multi]
        self.assertEqual(multi_paths, ['one', 'two'])
        self.assertEqual(action.name_update.question_path, None)

    def test_normalize_name_update_when_multiple_updates_exist_does_nothing(self):
        action = OpenCaseAction({
            'name_update_multi': [{'question_path': 'name1'}, {'question_path': 'name2'}]
        })

        action.normalize_name_update()

        self.assertIsNone(action.name_update.question_path)
        multi_paths = [update.question_path for update in action.name_update_multi]
        self.assertEqual(multi_paths, ['name1', 'name2'])

    def test_normalize_name_update_moves_name_update_multi_to_name_update(self):
        action = OpenCaseAction({
            'name_update_multi': [{'question_path': 'name'}]
        })

        action.normalize_name_update()

        self.assertEqual(action.name_update.question_path, 'name')
        self.assertIsNone(action.name_update_multi)

    def test_make_single_does_nothing_when_name_update_multi_is_empty(self):
        action = OpenCaseAction({
            'name_update': {'question_path': 'name'}
        })

        action.make_single()
        self.assertEqual(action.name_update.question_path, 'name')
        self.assertEqual(action.name_update_multi, [])

    def test_make_single_takes_the_last_entry_for_conflicting_case_properties(self):
        action = OpenCaseAction({
            'name_update_multi': [{'question_path': 'name1'}, {'question_path': 'name2'}]
        })

        action.make_single()
        self.assertEqual(action.name_update.question_path, 'name2')
        self.assertEqual(action.name_update_multi, None)


class OpenCaseAction_ApplyUpdates_Tests(SimpleTestCase):
    def test_no_changes(self):
        action = OpenCaseAction({'name_update': {'question_path': 'name'}})

        action.apply_updates({}, OpenCaseDiff({}))

        self.assertEqual(action.name_update.question_path, 'name')

    def test_name_update(self):
        action = OpenCaseAction({'name_update': {'question_path': 'name'}})

        action.apply_updates({}, OpenCaseDiff({'add': [{'question_path': 'new_name'}]}))

        multi_paths = [update.question_path for update in action.name_update_multi]
        self.assertEqual(multi_paths, ['name', 'new_name'])

    def test_with_conditional_update(self):
        action = OpenCaseAction({'name_update': {'question_path': 'name'}})

        update_condition_dict = {'condition': {'type': 'if', 'question': 'name', 'answer': 'bob', 'operator': '='}}
        action.apply_updates(update_condition_dict, OpenCaseDiff({}))

        self.assertEqual(action.condition.type, 'if')
        self.assertEqual(action.condition.question, 'name')
        self.assertEqual(action.condition.answer, 'bob')
        self.assertEqual(action.condition.operator, '=')

    def test_can_assign_with_update(self):
        action = OpenCaseAction({'name_update': {'question_path': 'name'}})

        action.apply_updates({'name_update': {'question_path': 'name2'}}, OpenCaseDiff({}))

        self.assertEqual(action.name_update.question_path, 'name2')

    def test_diffs_override_updates(self):
        action = OpenCaseAction({'name_update': {'question_path': 'name'}})

        update = {'name_update': {'question_path': 'name2', 'update_mode': 'always'}}
        diff = {'update': [{'question_path': 'name2', 'update_mode': 'edit'}]}
        action.apply_updates(update, OpenCaseDiff(diff))

        self.assertEqual(action.name_update.update_mode, 'edit')

    def test_with_invalid_key_raises_exception(self):
        action = OpenCaseAction({'name_update': {'question_path': 'name'}})
        with self.assertRaises(InvalidPropertyException):
            action.apply_updates({'invalid_property': {}}, OpenCaseDiff({}))

    def test_conflicting_name_addition_is_overwritten(self):
        action = OpenCaseAction({'name_update': {'question_path': 'name', 'update_mode': 'always'}})

        action.apply_updates({}, OpenCaseDiff({'add': [{'question_path': 'name', 'update_mode': 'edit'}]}))

        self.assertEqual(action.name_update.question_path, 'name')
        self.assertEqual(action.name_update.update_mode, 'edit')

    def test_apply_updates_remove_name(self):
        action = OpenCaseAction({'name_update_multi': [{'question_path': 'name1'}, {'question_path': 'name2'}]})

        action.apply_updates({}, OpenCaseDiff({'delete': [{'question_path': 'name1'}]}))

        self.assertEqual(action.name_update.question_path, 'name2')

    def test_apply_updates_remove_name_does_nothing_when_name_is_absent(self):
        action = OpenCaseAction({'name_update': {'question_path': 'name2'}})

        action.apply_updates({}, OpenCaseDiff({'delete': [{'question_path': 'name1'}]}))

        self.assertEqual(action.name_update.question_path, 'name2')

    def test_apply_updates_update_name(self):
        action = OpenCaseAction({'name_update': {'question_path': 'name'}})

        action.apply_updates({}, OpenCaseDiff({'update': [{'question_path': 'name', 'update_mode': 'edit'}]}))

        self.assertEqual(action.name_update.update_mode, 'edit')

    def test_apply_updates_updating_missing_name_raises_error(self):
        action = OpenCaseAction({'name_update': {'question_path': 'name'}})

        with self.assertRaises(MissingPropertyMapException):
            diff = OpenCaseDiff({'update': [{'question_path': 'missing_name', 'update_mode': 'edit'}]})
            action.apply_updates({}, diff)


class UpdateCaseActionTests(SimpleTestCase):
    def test_construction(self):
        action = UpdateCaseAction({
            'update': {'one': {'question_path': '/root/'}},
            'update_multi': {
                'two': [
                    {'question_path': '/one/'},
                    {'question_path': '/two/'},
                ]
            }
        })

        self.assertEqual(action.update['one'].question_path, '/root/')
        multi_paths = {k: [action.question_path for action in v] for (k, v) in action.update_multi.items()}
        self.assertEqual(multi_paths, {'two': ['/one/', '/two/']})

    def test_make_multi_when_no_updates_does_nothing(self):
        action = UpdateCaseAction({
            'update_multi': {
                'two': [
                    {'question_path': '/one/'},
                    {'question_path': '/two/'},
                ]
            }
        })

        changed = action.make_multi()

        self.assertFalse(changed)
        multi_paths = {k: [action.question_path for action in v] for (k, v) in action.update_multi.items()}
        self.assertEqual(multi_paths, {'two': ['/one/', '/two/']})

    def test_make_multi_when_updates_are_none_does_nothing(self):
        action = UpdateCaseAction({
            'update': None,
            'update_multi': {
                'two': [
                    {'question_path': '/one/'},
                    {'question_path': '/two/'},
                ]
            }
        })

        changed = action.make_multi()

        self.assertFalse(changed)
        multi_paths = {k: [action.question_path for action in v] for (k, v) in action.update_multi.items()}
        self.assertEqual(multi_paths, {'two': ['/one/', '/two/']})

    def test_make_multi_populates_multi(self):
        action = UpdateCaseAction({
            'update': {
                'one': {'question_path': '/one/'},
                'two': {'question_path': '/two/'},
            }
        })

        changed = action.make_multi()

        self.assertTrue(changed)
        multi_paths = {k: [action.question_path for action in v] for (k, v) in action.update_multi.items()}
        self.assertEqual(multi_paths, {'one': ['/one/'], 'two': ['/two/']})
        self.assertEqual(action.update, {})

    def test_normalize_update_when_case_property_has_multiple_questions_does_nothing(self):
        action = UpdateCaseAction({
            'update_multi': {
                'one': [
                    {'question_path': '/one/'},
                    {'question_path': '/two/'}
                ]
            }
        })

        applied = action.normalize_update()

        self.assertFalse(applied)
        self.assertEqual(action.update, {})

    def test_normalize_update_moves_update_multi_to_update(self):
        action = UpdateCaseAction({
            'update_multi': {
                'one': [{'question_path': '/one/'}],
                'two': [{'question_path': '/two/'}]
            }
        })

        applied = action.normalize_update()

        update_paths = {k: v.question_path for (k, v) in action.update.items()}

        self.assertTrue(applied)
        self.assertEqual(update_paths, {'one': '/one/', 'two': '/two/'})
        self.assertIsNone(action.update_multi)

    def test_normalize_update_removes_empty_keys(self):
        action = UpdateCaseAction({
            'update_multi': {
                'one': []
            }
        })

        action.normalize_update()

        self.assertNotIn('one', action.update)
        self.assertIsNone(action.update_multi)

    def test_make_single_does_nothing_when_update_multi_is_empty(self):
        action = UpdateCaseAction({
            'update': {
                'one': {'question_path': '/one/'}
            }
        })

        action.make_single()
        self.assertEqual(action.update['one'].question_path, '/one/')
        self.assertEqual(action.update_multi, {})

    def test_make_single_takes_the_last_entry_for_conflicting_case_properties(self):
        action = UpdateCaseAction({
            'update_multi': {
                'one': [{'question_path': '/one/'}, {'question_path': '/two/'}]
            }
        })

        action.make_single()
        self.assertEqual(action.update['one'].question_path, '/two/')
        self.assertEqual(action.update_multi, None)


class UpdateCaseAction_ApplyUpdates_Tests(SimpleTestCase):
    def test_no_changes(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'}
        }})

        actions.apply_updates({}, UpdateCaseDiff({}))

        self.assertEqual(actions.update['one'].question_path, 'one')

    def test_add_value_no_conflict(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
            'two': {'question_path': 'two'},
        }})

        actions.apply_updates({}, UpdateCaseDiff({
            'add': {'three': [{'question_path': 'some_path'}]},
        }))

        self.assertEqual(set(actions.update.keys()), {'one', 'two', 'three'})

    def test_add_value_creates_conflict(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'question1'}
        }})

        actions.apply_updates({}, UpdateCaseDiff({
            'add': {'one': [{'question_path': 'question2'}]}
        }))

        self.assertEqual(actions.update, {})
        self.assertEqual(set(actions.update_multi.keys()), {'one'})
        paths = [update.question_path for update in actions.update_multi['one']]
        self.assertEqual(set(paths), {'question1', 'question2'})

    def test_add_value_overwrites_value_when_conflicts_are_prohibited(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'question1'}
        }})

        actions.apply_updates({}, UpdateCaseDiff({
            'add': {'one': [{'question_path': 'question2'}]}
        }), allow_conflicts=False)

        self.assertEqual(actions.update['one'].question_path, 'question2')
        self.assertIsNone(actions.update_multi)

    def test_add_value_with_existing_conflict(self):
        actions = UpdateCaseAction({'update_multi': {
            'one': [{'question_path': 'question1'}, {'question_path': 'question2'}]
        }})

        actions.apply_updates({}, UpdateCaseDiff({
            'add': {'one': [{'question_path': 'question3'}]}
        }))

        self.assertEqual(set(actions.update_multi.keys()), {'one'})
        paths = [update.question_path for update in actions.update_multi['one']]
        self.assertEqual(set(paths), {'question1', 'question2', 'question3'})

    def test_adding_duplicate_property_does_nothing(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'question1'}
        }})

        actions.apply_updates({}, UpdateCaseDiff({
            'add': {'one': [{'question_path': 'question1'}]}
        }))

        self.assertEqual(set(actions.update.keys()), {'one'})
        self.assertEqual(actions.update['one'].question_path, 'question1')

    def test_adding_existing_modified_property_overwrites_the_property(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one', 'update_mode': 'always'},
        }})

        actions.apply_updates({}, UpdateCaseDiff({
            'add': {'one': [{'question_path': 'one', 'update_mode': 'edit'}]},
        }))

        self.assertEqual(actions.update['one'].update_mode, 'edit')

    def test_remove_value(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
            'two': {'question_path': 'two'},
        }})

        actions.apply_updates({}, UpdateCaseDiff({
            'delete': {'one': [{'question_path': 'one'}]},
        }))

        self.assertEqual(set(actions.update.keys()), {'two'})

    def test_deleting_a_missing_property_does_nothing(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
        }})

        actions.apply_updates({}, UpdateCaseDiff({'delete': {'one': [{'question_path': 'two'}]}}))

        self.assertEqual(actions.update.keys(), {'one'})
        self.assertEqual(actions.update['one'].question_path, 'one')

    def test_update_value(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'question_one', 'update_mode': 'always'},
        }})

        actions.apply_updates({}, UpdateCaseDiff({
            'update': {
                'one': [{'question_path': 'question_one', 'update_mode': 'edit'}],
            }
        }))

        self.assertEqual(actions.update['one'].update_mode, 'edit')

    def test_updating_a_missing_property_raises_error(self):
        # If a property was deleted by a different session, updating it shouldn't restore it
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'question_one'},
        }})

        with self.assertRaises(MissingPropertyMapException):
            actions.apply_updates({}, UpdateCaseDiff({
                'update': {'two': [{'question_path': 'question_two', 'update_mode': 'edit'}]}
            }))

    def test_updating_a_missing_question_raises_error(self):
        # If the specific mapping was deleted by a different session, updating it shouldn't restore it
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'question_one'}
        }})

        with self.assertRaises(MissingPropertyMapException):
            actions.apply_updates({}, UpdateCaseDiff({
                'update': {
                    'one': [{'question_path': 'question_two', 'update_mode': 'edit'}]
                }
            }))

    def test_missing_property_exception_contains_all_missing_properties(self):
        actions = UpdateCaseAction({'update': {}})

        with self.assertRaises(MissingPropertyMapException) as context:
            actions.apply_updates({}, UpdateCaseDiff({
                'update': {
                    'one': [{'question_path': 'question_one', 'update_mode': 'always'}],
                    'two': [{'question_path': 'question_two', 'update_mode': 'edit'}],
                }
            }))

        self.assertEqual(list(context.exception.missing_mappings), [
            {'case_property': 'one', 'question_path': 'question_one'},
            {'case_property': 'two', 'question_path': 'question_two'}
        ])

    def test_multiple_actions_attempting_to_affect_the_same_key_raises_error(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
            'two': {'question_path': 'two'},
        }})

        with self.assertRaises(DiffConflictException):
            actions.apply_updates({}, UpdateCaseDiff({
                'update': {'two': [{'question_path': 'question_two', 'update_mode': 'always'}]},
                'delete': {'two': [{'question_path': 'question_two'}]}
            }))

    def test_updates_no_diffs(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'}
        }})

        actions.apply_updates({'update': {'one': {'question_path': 'two'}}}, UpdateCaseDiff({}))

        self.assertEqual(actions.update['one'].question_path, 'two')

    def test_updates_condition(self):
        actions = UpdateCaseAction()

        actions.apply_updates({'condition': {'type': 'never'}}, UpdateCaseDiff({}))
        self.assertEqual(actions.condition.type, 'never')

    def test_diffs_override_updates(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
        }})

        updates = {
            'update': {'one': {'question_path': 'one', 'update_mode': 'always'}}
        }
        diffs = UpdateCaseDiff({
            'update': {
                'one': [{'question_path': 'one', 'update_mode': 'edit'}]
            }
        })
        actions.apply_updates(updates, diffs)

        self.assertEqual(actions.update['one'].update_mode, 'edit')


class FormActionsTests(SimpleTestCase):
    def test_constructor_creates_empty_values(self):
        actions = FormActions()
        self.assertEqual(actions.update_case.update, {})


class FormActions_WithUpdatesTests(SimpleTestCase):
    def test_empty_diff(self):
        actions = FormActions({
            'open_case': {
                'name_update': {'question_path': 'name'},
            },
            'update_case': {
                'update': {
                    'one': {'question_path': 'one'},
                    'two': {'question_path': 'two'},
                }
            }
        })

        result = actions.with_updates({}, FormActionsDiff({}))

        self.assertEqual(result['open_case']['name_update']['question_path'], 'name')
        self.assertEqual(list(result['update_case']['update'].keys()), ['one', 'two'])

    def test_other_updates(self):
        # i.e. not open_case or update_case
        actions = FormActions()

        close_case_update = {'close_case': {'condition': {'type': 'never'}}}

        result = actions.with_updates(close_case_update, FormActionsDiff({}))

        self.assertEqual(result.close_case.condition.type, 'never')

    def test_all_actions_at_once(self):
        actions = FormActions({
            'open_case': {
                'name_update': {'question_path': 'form_name'},
            },
            'update_case': {
                'update': {
                    'one': {'question_path': 'one'},
                    'two': {'question_path': 'two'},
                }
            }
        })

        result = actions.with_updates({}, FormActionsDiff({
            'open_case': {
                'add': [{'question_path': 'new_name'}],
                'delete': [{'question_path': 'form_name'}],
            },
            'update_case': {
                'add': {'three': [{'question_path': 'three'}]},
                'delete': {'one': [{'question_path': 'one'}]},
                'update': {
                    'two': [{'question_path': 'two', 'update_mode': 'edit'}]
                }
            }
        }))

        self.assertEqual(result.open_case.name_update.question_path, 'new_name')
        self.assertEqual(set(result.update_case.update.keys()), {'two', 'three'})
        self.assertEqual(result.update_case.update['two'].update_mode, 'edit')


class OpenCaseDiffTests(SimpleTestCase):
    def test_construction_with_all_values(self):
        diff = OpenCaseDiff({
            'add': [{'question_path': 'one'}, {'question_path': 'two'}],
            'delete': [{'question_path': 'three'}, {'question_path': 'four'}],
            'update': [{'question_path': 'five', 'update_mode': 'edit'}]
        })

        add_questions = [question.question_path for question in diff.add]
        delete_questions = [question.question_path for question in diff.delete]
        assert add_questions == ['one', 'two']
        assert delete_questions == ['three', 'four']
        assert diff.update[0].update_mode == 'edit'

    def test_convert_to_update_diff(self):
        diff = OpenCaseDiff({
            'add': [{'question_path': 'one'}],
            'delete': [{'question_path': 'two'}],
            'update': [{'question_path': 'three', 'update_mode': 'edit'}]
        })

        update_diff = diff.convert_to_update_diff()

        assert [question.question_path for question in update_diff.add['name_update_multi']] == ['one']
        assert [question.question_path for question in update_diff.delete['name_update_multi']] == ['two']
        assert update_diff.update['name_update_multi'][0].update_mode == 'edit'

    def test_convert_to_update_diff_only_includes_populated_values(self):
        diff = OpenCaseDiff({
            'delete': [{'question_path': 'one'}]
        })

        update_diff = diff.convert_to_update_diff()

        assert [question.question_path for question in update_diff.delete['name_update_multi']] == ['one']
        assert update_diff.add == {}
        assert update_diff.update == {}


class UpdateCaseDiffTests(SimpleTestCase):
    def test_construction_with_all_values(self):
        diff = UpdateCaseDiff({
            'add': {
                'case_one': [{'question_path': 'one'}],
                'case_two': [{'question_path': 'two'}]
            },
            'delete': {
                'case_three': [{'question_path': 'three'}, {'question_path': 'four'}]
            },
            'update': {
                'case_four': [{'question_path': 'five', 'update_mode': 'edit'}]
            }
        })

        assert diff.add['case_one'][0].question_path == 'one'
        assert diff.add['case_two'][0].question_path == 'two'

        assert [question.question_path for question in diff.delete['case_three']] == ['three', 'four']

        assert diff.update['case_four'][0].update_mode == 'edit'


class FormActionsDiffTests(SimpleTestCase):
    def test_json_construction(self):
        diff = FormActionsDiff({
            'open_case': {
                'add': [{'question_path': 'one'}]
            },
            'update_case': {
                'delete': {
                    'case_two': [{'question_path': 'two'}]
                }
            }
        })

        assert diff.open_case.add[0].question_path == 'one'
        assert diff.update_case.delete['case_two'][0].question_path == 'two'
