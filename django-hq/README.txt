
Commcare-HQ Overall project structure.

apps/
	Django apps that you will make
	
	
libs/
	Any third party libs (presumably python) that you'll need to reference
	
scripts/
	Any helper scripts you'll want to write to deal with data and or other things.  This stuff should probably run outside the scope of the python environment
	
projects/
	Directory where your django projects will reside.  This is taken from the pinax project structure
	Projects will need to reference ../../apps/ to get to the apps that are referenced in the settings.py
	As new apps are created, you'll either have to expand your project or make new projects that reference the new apps
	Pinax uses these to show different configurations of their project.
	
projects/templates/
	for each project, there needs to be templates unique to managing the templates for the main content portions.
	within the confines of the application you're working in, you can make templates local and relative to the application you create.
	
	 