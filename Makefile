.PHONY: requirements

requirements: export CUSTOM_COMPILE_COMMAND=make requirements
requirements:
	pip-compile --upgrade -o requirements/requirements.txt requirements/requirements.in
	pip-compile --upgrade -o requirements/prod-requirements.txt requirements/prod-requirements.in --allow-unsafe
