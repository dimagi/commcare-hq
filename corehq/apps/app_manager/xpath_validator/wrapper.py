import re
import subprocess
from collections import namedtuple

from corehq.apps.app_manager.xpath_validator.config import (
    get_xpath_validator_path,
)
from corehq.apps.app_manager.xpath_validator.exceptions import (
    XpathValidationError,
)

XpathValidationResponse = namedtuple('XpathValidationResponse', ['is_valid', 'message'])


def validate_xpath(xpath, allow_case_hashtags=False):
    path = get_xpath_validator_path()
    if allow_case_hashtags:
        cmd = ['node', path, '--allow-case-hashtags']
    else:
        cmd = ['node', path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Collapse whitespace. '\r' mysteriously causes the process to hang in python 3.
    stdout, stderr = p.communicate(re.sub(r'\s+', ' ', xpath).encode('utf-8'))
    exit_code = p.wait()
    if exit_code == 0:
        return XpathValidationResponse(is_valid=True, message=None)
    elif exit_code == 1:
        return XpathValidationResponse(is_valid=False, message=stdout)
    else:
        raise XpathValidationError(
            "{path} failed with exit code {exit_code}:\n{stderr}"
            .format(path=path, exit_code=exit_code, stderr=stderr))
