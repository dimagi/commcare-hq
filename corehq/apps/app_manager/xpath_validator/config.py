import os


def get_xpath_validator_path():
    return os.path.join(
        os.path.abspath(os.path.dirname(__file__)), "js", "xpathValidator.js")
