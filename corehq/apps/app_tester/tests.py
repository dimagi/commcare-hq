import yaml


def test_yaml_parses():
    data = yaml.load('app_tester_sample.yaml')  # TODO: path
    assert data  # <3 nosetests


def test_open_session():
    pass


def test_iter_questions():
    pass
