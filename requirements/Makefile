.PHONY: requirements upgrade-requirements

requirements: export CUSTOM_COMPILE_COMMAND=`make requirements` or `make upgrade-requirements`
requirements:
	pip-compile -o requirements.txt requirements.in --allow-unsafe
	pip-compile -o prod-requirements.txt prod-requirements.in --allow-unsafe
	pip-compile -o test-requirements.txt test-requirements.in --allow-unsafe
	pip-compile -o dev-requirements.txt dev-requirements.in --allow-unsafe
	pip-compile -o docs-requirements.txt docs-requirements.in --allow-unsafe
	awk 'BEGIN { del=0 } /appnope/ { del=1 } del<=0 { print } /via ipython/ { del -= 1 }' prod-requirements.txt > temp-prod-requirements.txt && mv temp-prod-requirements.txt prod-requirements.txt
	awk 'BEGIN { del=0 } /appnope/ { del=1 } del<=0 { print } /via ipython/ { del -= 1 }' dev-requirements.txt > temp-dev-requirements.txt && mv temp-dev-requirements.txt dev-requirements.txt

upgrade-requirements: export CUSTOM_COMPILE_COMMAND=`make requirements` or `make upgrade-requirements`
upgrade-requirements:
	pip-compile --upgrade -o requirements.txt requirements.in --allow-unsafe
	pip-compile --upgrade -o prod-requirements.txt prod-requirements.in --allow-unsafe
	pip-compile --upgrade -o test-requirements.txt test-requirements.in --allow-unsafe
	pip-compile --upgrade -o dev-requirements.txt dev-requirements.in --allow-unsafe
	pip-compile --upgrade -o docs-requirements.txt docs-requirements.in --allow-unsafe
	awk 'BEGIN { del=0 } /appnope/ { del=1 } del<=0 { print } /via ipython/ { del -= 1 }' prod-requirements.txt > temp-prod-requirements.txt && mv temp-prod-requirements.txt prod-requirements.txt
	awk 'BEGIN { del=0 } /appnope/ { del=1 } del<=0 { print } /via ipython/ { del -= 1 }' dev-requirements.txt > temp-dev-requirements.txt && mv temp-dev-requirements.txt dev-requirements.txt
