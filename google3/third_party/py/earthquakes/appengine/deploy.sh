#!/bin/bash

blaze build  third_party/py/earthquakes/appengine:earthquakes
/google/data/ro/buildstatic/projects/apphosting/tools/appcfg_over_stubby.par \
  update blaze-bin/third_party/py/earthquakes/appengine/earthquakes.runfiles
