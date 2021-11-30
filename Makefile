.PHONY: requirements upgrade-requirements docs migrations

requirements:
	cd requirements && $(MAKE) requirements

upgrade-requirements:
	cd requirements && $(MAKE) upgrade-requirements

docs:
	cd docs && $(MAKE) html; cd -

migrations: TMPLOCK:=migrations.new.lock
migrations:
	./manage.py showmigrations --list > $(TMPLOCK) || (rc=$$?; rm -vf $(TMPLOCK); exit $$rc)
	@if diff --color /dev/null /dev/null >/dev/null 2>&1; then \
		diffcolor=--color; \
	fi; \
	diff $$diffcolor -su migrations.lock $(TMPLOCK) || true
	mv $(TMPLOCK) migrations.lock
