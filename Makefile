.PHONY: requirements upgrade-requirements docs

# https://stackoverflow.com/questions/4933285/how-to-detemine-python-version-in-makefile
python_version_full := $(wordlist 2,4,$(subst ., ,$(shell python --version 2>&1)))
python_version_major := $(word 1,${python_version_full})

REQUIREMENTS_TXT_DIR=requirements

requirements: export CUSTOM_COMPILE_COMMAND=`make requirements` or `make upgrade-requirements`
requirements:
	pip-compile -o $(REQUIREMENTS_TXT_DIR)/requirements.txt requirements/requirements.in --allow-unsafe
	pip-compile -o $(REQUIREMENTS_TXT_DIR)/prod-requirements.txt requirements/prod-requirements.in --allow-unsafe
	pip-compile -o $(REQUIREMENTS_TXT_DIR)/test-requirements.txt requirements/test-requirements.in --allow-unsafe
	pip-compile -o $(REQUIREMENTS_TXT_DIR)/dev-requirements.txt requirements/dev-requirements.in --allow-unsafe
	scripts/pip-post-compile.sh $(REQUIREMENTS_TXT_DIR)/*requirements.txt
	cp $(REQUIREMENTS_TXT_DIR)/*requirements.txt requirements-python3/  # TODO remove once commcare-cloud no longer depends on it

upgrade-requirements: export CUSTOM_COMPILE_COMMAND=`make requirements` or `make upgrade-requirements`
upgrade-requirements:
	pip-compile --upgrade -o $(REQUIREMENTS_TXT_DIR)/requirements.txt requirements/requirements.in --allow-unsafe
	pip-compile --upgrade -o $(REQUIREMENTS_TXT_DIR)/prod-requirements.txt requirements/prod-requirements.in --allow-unsafe
	pip-compile --upgrade -o $(REQUIREMENTS_TXT_DIR)/test-requirements.txt requirements/test-requirements.in --allow-unsafe
	pip-compile --upgrade -o $(REQUIREMENTS_TXT_DIR)/dev-requirements.txt requirements/dev-requirements.in --allow-unsafe
	scripts/pip-post-compile.sh $(REQUIREMENTS_TXT_DIR)/*requirements.txt
	cp $(REQUIREMENTS_TXT_DIR)/*requirements.txt requirements-python3/  # TODO remove once commcare-cloud no longer depends on it

docs:
	cd docs && $(MAKE) html
