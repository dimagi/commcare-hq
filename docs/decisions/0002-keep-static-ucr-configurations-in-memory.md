# 2. Keep static UCR configurations in memory

Date: 2018-07-04

## Status

Accepted

## Context

As part of the UCR framework configurations for data sources and reports
may be stored in the database or as static files shipped with the code.

These static files can apply to many different domains and even different
server environments.

When a data source or report configuraiton is requested the static configuration
is read from disk and converted into the appropriate JsonObject class.

During some performance testing on ICDS it was noted that the process or
readying the static configuration files from disk and converting them
to the JsonObject classes was taking up significant time (14% of restore
time for ICDS).

## Decision

To improve the performance (primarily of restores) it was decided to maintain
the list of configurations in memeory rather than re-read them from disk
for each request.

In order to keep the memory footprint to a minimum only the static configurations
are kept in memory and not the generated classes. This also serves to ensure
that any modifications that may get made to the classes do not persist.

There are still some places that re-read the configurations from disk
each time but these not called in places that require high performance. An
example of this is the UCR pillow bootstrapping.

## Consequences

Although this may raise the memory usage of the processes (after the
configurations have been loaded) it should be noted that even in the current
setup all the configurations are loaded on first request in order to generate
the list of available data sources / reports. It may be that memory get's
released at some point after the initial load.

In terms of actual memory footprint the figures are as follows:

Base memory: 285Mb
Data sources: 60Mb
Report configs: 35Mb
