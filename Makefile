.PHONY: requirements upgrade-requirements docs

# https://stackoverflow.com/questions/4933285/how-to-detemine-python-version-in-makefile
python_version_full := $(wordlist 2,4,$(subst ., ,$(shell python --version 2>&1)))
python_version_major := $(word 1,${python_version_full})

ifeq (${python_version_major}, 2)
REQUIREMENTS_TXT_DIR=requirements
else
REQUIREMENTS_TXT_DIR=requirements-python3
endif

requirements: export CUSTOM_COMPILE_COMMAND=`make requirements` or `make upgrade-requirements`
requirements:
	pip-compile -o $(REQUIREMENTS_TXT_DIR)/requirements.txt requirements/requirements.in
	pip-compile -o $(REQUIREMENTS_TXT_DIR)/prod-requirements.txt requirements/prod-requirements.in --allow-unsafe
	pip-compile -o $(REQUIREMENTS_TXT_DIR)/test-requirements.txt requirements/test-requirements.in
	pip-compile -o $(REQUIREMENTS_TXT_DIR)/dev-requirements.txt requirements/dev-requirements.in
	scripts/pip-post-compile.sh $(REQUIREMENTS_TXT_DIR)/*requirements.txt

upgrade-requirements: export CUSTOM_COMPILE_COMMAND=`make requirements` or `make upgrade-requirements`
upgrade-requirements:
	pip-compile --upgrade -o $(REQUIREMENTS_TXT_DIR)/requirements.txt requirements/requirements.in
	pip-compile --upgrade -o $(REQUIREMENTS_TXT_DIR)/prod-requirements.txt requirements/prod-requirements.in --allow-unsafe
	pip-compile --upgrade -o $(REQUIREMENTS_TXT_DIR)/test-requirements.txt requirements/test-requirements.in
	pip-compile --upgrade -o $(REQUIREMENTS_TXT_DIR)/dev-requirements.txt requirements/dev-requirements.in
	scripts/pip-post-compile.sh $(REQUIREMENTS_TXT_DIR)/*requirements.txt

docs:
	cd docs && $(MAKE) html
