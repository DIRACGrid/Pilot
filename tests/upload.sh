# Uploads a pilot.tar and a pilot.json to http://diracproject.web.cern.ch/diracproject/tars/Pilot/DIRAC/[directory]

# temp work dir
tmpdir=$(mktemp -d)
echo $tmpdir
cp Pilot/*.py $tmpdir
cp tests/pilot.json $tmpdir

# create the tar and upload
cd $tmpdir
tar -cf pilot.tar *.py
( tar -cf - pilot.tar pilot.json ) | ssh uploaduser@lxplus.cern.ch "cd /eos/project/d/diracgrid/www/tars/Pilot/DIRAC/${1}/ && tar -xvf - "
