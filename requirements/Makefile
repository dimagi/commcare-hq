.PHONY: requirements upgrade-requirements

requirements: export CUSTOM_COMPILE_COMMAND=`make requirements` or `make upgrade-requirements`
requirements:
	pip-compile -o requirements.txt requirements.in --allow-unsafe
	pip-compile -o prod-requirements.txt prod-requirements.in --allow-unsafe
	pip-compile -o test-requirements.txt test-requirements.in --allow-unsafe
	pip-compile -o dev-requirements.txt dev-requirements.in --allow-unsafe

upgrade-requirements: export CUSTOM_COMPILE_COMMAND=`make requirements` or `make upgrade-requirements`
upgrade-requirements:
	pip-compile --upgrade -o requirements.txt requirements.in --allow-unsafe
	pip-compile --upgrade -o prod-requirements.txt prod-requirements.in --allow-unsafe
	pip-compile --upgrade -o test-requirements.txt test-requirements.in --allow-unsafe
	pip-compile --upgrade -o dev-requirements.txt dev-requirements.in --allow-unsafe
