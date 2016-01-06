# Earthquakes Docker config file.


FROM debian:wheezy

MAINTAINER Jeremy Faller <jfaller@google.com>

# Add the linux packages we need. This was tested to be a relatively minimal
# list.
RUN apt-get update && \
  apt-get install -y \
    python-dev \
    python-pip \
    python-numpy \
    git \
    python-matplotlib \
    gfortran \
    python-shapely

# Get ez_setup. This is required by the okada_wrapper.
RUN wget https://bootstrap.pypa.io/ez_setup.py -O - | python

# Install all the python packages.
RUN pip install \
  git+http://github.com/tbenthompson/okada_wrapper \
  utm \
  requests \
  pyproj \
  geopy \
  google-api-python-client

# Finally copy over our code!
COPY *.py /

# And run it (32x, once per CPU).
CMD ["/usr/bin/python", "/earthquakes.py", "-j32"]
