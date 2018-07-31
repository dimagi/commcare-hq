.PHONY: requirements upgrade-requirements

requirements: export CUSTOM_COMPILE_COMMAND=make requirements
requirements:
	pip-compile -o requirements/requirements.txt requirements/requirements.in
	pip-compile -o requirements/prod-requirements.txt requirements/prod-requirements.in --allow-unsafe

upgrade-requirements: export CUSTOM_COMPILE_COMMAND=make upgrade-requirements
upgrade-requirements:
	pip-compile --upgrade -o requirements/requirements.txt requirements/requirements.in
	pip-compile --upgrade -o requirements/prod-requirements.txt requirements/prod-requirements.in --allow-unsafe
