Contributing to DIRAC/Pilot
===========================

:+1::tada: First off, thanks for taking the time to contribute! :tada::+1:

Feel free to propose changes to this document in a pull request.

Repository structure
====================

Due to the fact that we support only the production and the development versions,
for now only 2 branchs are present: *master*, and *devel*. 

* *master* is the stable branch. Production tags are created starting from this branch.
* *devel* is the development branch. Tags created starting from this branch are subject to a certification process.

The following diagram highlights the interactions between the branches and the merging and tagging strategy:
![LHCbDIRAC branches](https://docs.google.com/drawings/d/14UPBPGW2R8d7JBO9eHWw2tyD3ApEuUBmlDEFicoBs1U/pub?w=1011&h=726)

For now, actually there are no tags created yet, so we've always used the HEAD of the branches.

Repositories
============

Developers should have 2 remote repositories (which is the typical GitHub workflow):

* *origin* : cloned from your private fork done on GitHub
* *upstream* : add it via git remote add upstream and pointing to the blessed repository: git@github.com:DIRACGrid/Pilot.git (or https://github.com/DIRACGrid/Pilot.git using https protocol)

Issue Tracking
==============

Issue tracking for the project is [here in github](https://github.com/DIRACGrid/Pilot/issues). 


Code quality
============

The contributions are subject to reviews.

Pylint is run regularly on the source code. The .pylintrc file defines the expected coding rules and peculiarities.


Testing
======

Unit tests are provided within the source code. Integration, regression and system tests are instead in the tests directory.


