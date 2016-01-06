#!/bin/bash
# Copyright (c) 2015 Google, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

cmd=$1

PROJECT=shaky-foundation-02138
IMAGE=gcr.io/${PROJECT}/eq-docker-image
MACHINE=n1-highmem-32
SCOPES=https://www.googleapis.com/auth/devstorage.read_write

function start_instance {
  echo "Starting instance $1 $2"

  # Note, we could background all the start/stop operations by replacing the
  # '&&' below with '& &&'. You would probably also want to pipe output to
  # /dev/null.
  gcloud container clusters create $1 --zone=$2 --num-nodes $3 \
    --scopes=${SCOPES} --machine-type ${MACHINE} --network internal-only \
    --disk-size 2500 &&
  kubectl run $1 --image=${IMAGE} --replicas=$3
}

function stop_instance {
  echo "Stopping job $1 in zone $2"
  # Note we stop all jobs in parallel.
  yes | gcloud container clusters delete -z $2 $1 2&> /dev/null &
}

if [ "$cmd" == "start" ]
then
  # Build the docker instance.
  # Note we cd to the directory for this script, so this script must be in the
  # same directory as the python code, and Dockerfile.
  cd "$(dirname "$0")"
  docker build -t ${IMAGE} .
  gcloud docker push ${IMAGE}

  start_instance eq-central us-central1-b 1
  #start_instance eq-east us-east1-b 1
  #start_instance eq-europe europe-west1-c 1
  #start_instance eq-asia asia-east1-b 1
elif [ "$cmd" == "stop" ]
then
  stop_instance eq-central us-central1-b
  #stop_instance eq-east us-east1-b
  #stop_instance eq-europe europe-west1-c
  #stop_instance eq-asia asia-east1-b
else
  echo "argument error $cmd"
  exit
fi

# Wait for all jobs.
for job in $(jobs -p)
do
  echo "Waiting for job: $job"
  wait $job
done

echo "All jobs ${cmd}ed"
