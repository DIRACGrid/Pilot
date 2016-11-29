#!/bin/bash
#-------------------------------------------------------------------------------
#
# pilot_wrapper.sh
#
#-------------------------------------------------------------------------------
#
# Caracteristics:
#   * VO/communities agnostic
#   * IMMUTABLE!
#
# Args:
#   $1 : URL from where to get the pilot files
#   $2 : CE name
#   $3 : queue name
#
#-------------------------------------------------------------------------------

if [ $1 ]
then
  if [[ $1 == 'http'* ]]
  then
    wget --no-directories --recursive --no-parent --execute robots=off --reject 'index.html*' $1
  elif [[ $1 == 'file'* ]]
  then
    es=''
    cp "${1/file:\/\//$es}"/*.py .
    cp "${1/file:\/\//$es}"/*.json .
  fi
else
  echo "ERROR: no URL supplied"
  exit 1
fi


# Now run the pilot script
# X509_USER_PROXY=/scratch/plt/etc/grid-security/hostkey.pem \
python dirac-pilot.py \
--debug \
--Name $2 \
--Queue $3
