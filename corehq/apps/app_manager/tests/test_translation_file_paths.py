from testil import eq

import commcare_translations


def test_version_paths_language_only():
    eq(
        commcare_translations.get_translation_file_paths('en'),
        ['../messages_en-1.txt']
    )


def test_version_paths_with_two_versions():
    eq(
        commcare_translations.get_translation_file_paths('en', version=2),
        ['../messages_en-2.txt', '../messages_en-1.txt']
    )


def test_version_paths_with_latest_commcare_version():
    eq(
        commcare_translations.get_translation_file_paths('en', version=1, commcare_version='latest'),
        ['../historical-translations-by-version/2.53-messages_en-2.txt', '../messages_en-1.txt']
    )


def test_version_paths_with_latest_commcare_version_and_two_versions():
    eq(
        commcare_translations.get_translation_file_paths('en', version=2, commcare_version='latest'),
        [
            '../historical-translations-by-version/2.53-messages_en-2.txt',
            '../messages_en-2.txt',
            '../messages_en-1.txt',
        ]
    )


def test_version_paths_with_commcare_version_less_than_2_23():
    eq(
        commcare_translations.get_translation_file_paths('en', version=1, commcare_version='2.2'),
        ['../messages_en-1.txt']
    )


def test_version_paths_with_commcare_version_less_than_2_23_and_two_versions():
    eq(
        commcare_translations.get_translation_file_paths('en', version=2, commcare_version='2.2'),
        [
            '../historical-translations-by-version/2.23-messages_en-2.txt',
            '../messages_en-2.txt',
            '../messages_en-1.txt',
        ]
    )


def test_version_paths_with_commcare_version_less_than_2_23_and_three_versions():
    eq(
        commcare_translations.get_translation_file_paths('en', version=3, commcare_version='2.2'),
        ['../messages_en-3.txt', '../messages_en-2.txt', '../messages_en-1.txt']
    )


def test_fr_version_paths_with_commcare_version_less_than_2_23():
    eq(
        commcare_translations.get_translation_file_paths('fr', version=1, commcare_version='2.2'),
        ['../messages_fr-1.txt']
    )


def test_fr_version_paths_with_commcare_version_less_than_2_23_and_two_versions():
    eq(
        commcare_translations.get_translation_file_paths('fr', version=2, commcare_version='2.2'),
        ['../messages_fr-2.txt', '../messages_fr-1.txt']
    )


def test_fr_version_paths_with_commcare_version_less_than_2_23_and_three_versions():
    eq(
        commcare_translations.get_translation_file_paths('fr', version=3, commcare_version='2.2'),
        ['../messages_fr-3.txt', '../messages_fr-2.txt', '../messages_fr-1.txt']
    )


def test_version_paths_with_commcare_version_later_than_2_23():
    eq(
        commcare_translations.get_translation_file_paths('en', version=1, commcare_version='2.42'),
        ['../messages_en-1.txt']
    )


def test_version_paths_with_commcare_version_later_than_2_23_and_two_versions():
    eq(
        commcare_translations.get_translation_file_paths('en', version=2, commcare_version='2.42'),
        [
            '../historical-translations-by-version/2.42-messages_en-2.txt',
            '../messages_en-2.txt',
            '../messages_en-1.txt',
        ]
    )


def test_version_paths_with_commcare_version_later_than_2_23_and_three_versions():
    eq(
        commcare_translations.get_translation_file_paths('en', version=3, commcare_version='2.42'),
        ['../messages_en-3.txt', '../messages_en-2.txt', '../messages_en-1.txt']
    )


def test_fr_version_paths_with_commcare_version_later_than_2_23():
    eq(
        commcare_translations.get_translation_file_paths('fr', version=1, commcare_version='2.42'),
        ['../messages_fr-1.txt']
    )


def test_fr_version_paths_with_commcare_version_later_than_2_23_and_two_versions():
    eq(
        commcare_translations.get_translation_file_paths('fr', version=2, commcare_version='2.42'),
        ['../messages_fr-2.txt', '../messages_fr-1.txt']
    )


def test_fr_version_paths_with_commcare_version_later_than_2_23_and_three_versions():
    eq(
        commcare_translations.get_translation_file_paths('fr', version=3, commcare_version='2.42'),
        ['../messages_fr-3.txt', '../messages_fr-2.txt', '../messages_fr-1.txt']
    )


def test_version_paths_with_commcare_version_less_than_2_23_with_bugfix():
    eq(
        commcare_translations.get_translation_file_paths('en', version=1, commcare_version='2.2.3'),
        ['../messages_en-1.txt']
    )


def test_version_paths_with_commcare_version_less_than_2_23_and_two_versions_with_bugfix():
    eq(
        commcare_translations.get_translation_file_paths('en', version=2, commcare_version='2.2.3'),
        [
            '../historical-translations-by-version/2.23-messages_en-2.txt',
            '../messages_en-2.txt',
            '../messages_en-1.txt',
        ]
    )


def test_version_paths_with_commcare_version_less_than_2_23_and_three_versions_with_bugfix():
    eq(
        commcare_translations.get_translation_file_paths('en', version=3, commcare_version='2.2.3'),
        ['../messages_en-3.txt', '../messages_en-2.txt', '../messages_en-1.txt']
    )


def test_version_paths_with_commcare_version_2_23_with_bugfix():
    eq(
        commcare_translations.get_translation_file_paths('en', version=1, commcare_version='2.23.3'),
        ['../messages_en-1.txt']
    )


def test_version_paths_with_commcare_version_2_23_and_two_versions_with_bugfix():
    eq(
        commcare_translations.get_translation_file_paths('en', version=2, commcare_version='2.23.3'),
        [
            '../historical-translations-by-version/2.23.3-messages_en-2.txt',
            '../historical-translations-by-version/2.23.2-messages_en-2.txt',
            '../historical-translations-by-version/2.23.1-messages_en-2.txt',
            '../historical-translations-by-version/2.23-messages_en-2.txt',
            '../messages_en-2.txt',
            '../messages_en-1.txt',
        ]
    )


def test_version_paths_with_commcare_version_2_23_and_three_versions_with_bugfix():
    eq(
        commcare_translations.get_translation_file_paths('en', version=3, commcare_version='2.23.3'),
        ['../messages_en-3.txt', '../messages_en-2.txt', '../messages_en-1.txt']
    )


def test_version_paths_with_commcare_version_2_23_beta_and_two_versions_with_bugfix():
    eq(
        commcare_translations.get_translation_file_paths('en', version=2, commcare_version='2.23.3beta2'),
        [
            '../historical-translations-by-version/2.23.3-messages_en-2.txt',
            '../historical-translations-by-version/2.23.2-messages_en-2.txt',
            '../historical-translations-by-version/2.23.1-messages_en-2.txt',
            '../historical-translations-by-version/2.23-messages_en-2.txt',
            '../messages_en-2.txt',
            '../messages_en-1.txt',
        ]
    )


def test_version_paths_with_commcare_version_2_23_beta_and_two_versions():
    eq(
        commcare_translations.get_translation_file_paths('en', version=2, commcare_version='2.23beta2'),
        [
            '../historical-translations-by-version/2.23-messages_en-2.txt',
            '../messages_en-2.txt',
            '../messages_en-1.txt',
        ]
    )


def test_version_paths_with_commcare_version_2_23_invalid_and_two_versions():
    # 2.23++ should return commcare_version = None
    eq(
        commcare_translations.get_translation_file_paths('en', version=2, commcare_version='2.23++'),
        ['../messages_en-2.txt', '../messages_en-1.txt']
    )


def test_version_paths_with_commcare_version_3_two_versions():
    eq(
        commcare_translations.get_translation_file_paths('en', version=2, commcare_version='3.0.0'),
        [
            '../historical-translations-by-version/3.0-messages_en-2.txt',
            '../messages_en-2.txt',
            '../messages_en-1.txt',
        ]
    )
