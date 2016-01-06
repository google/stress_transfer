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
"""Reads Srcmod data from .fsp files.

The original srcmod reader was a little fragile, failing to read in many of the
.mat files. ReadSrcmodFile fixes this -- it reads in the raw ascii from a .fsp
file, and returns the data in the same format. There are some small differences
in the data, mostly due to the fact that .mat files are 64-bit, and we read
in the ascii, and covert to floats. As such, there's some small differences in
the read in values, but this routine does work with all the data.
"""


import collections
import datetime
import logging
import math
import re

import gcs
import numpy as np
import pyproj
import utm


# Regular expressions that will parse the text Srcmod files.
# TAGS are of the form: 'xxx : yyy zzz'
TAGS_RE = re.compile(r'(\w+\s*:\s*(?:\S+ ?)+)')
# FIELDS are of the form: 'xxxx = float'
FIELDS_RE = re.compile(r'\w+\s+=\s+\-?\d+\.?\d*[eE]?[\+\-]?\d*')
# DATES are of the form: 'nn/nn/nn'
DATE_RE = re.compile(r'\d+/\d+/\d+')
# DATA fields within a segment begin with '% LAT LON'
DATA_FIELDS_RE = re.compile(r'%\s+LAT\s+LON')

# Maps tags between what's given in the srcmod file, and the output fields we
# use.
TAG_MAP = [
    ('EVENTTAG', 'tag'),
    ('EVENT', 'description'),
]

# There are a number of data fields from the header of a Srcmod file that are
# directly copied over into the output of the file reader. This is an array of
# the tuples where:
#
#     (INPUT_NAME, OUTPUT_NAME)
FIELD_MAP = [
    ('LAT', 'epicenterLatitude'),
    ('LON', 'epicenterLongitude'),
    ('DEP', 'depth'),
    ('MW', 'magnitude'),
    ('MO', 'moment'),
]

# Constants to do some conversions.
KM2M = 1e3  # Convert kilometers to meters
CM2M = 1e-2  # Convert centimeters to meters


def _FindFields(data, opt_ignore_duplicate=True):
  """Finds all 'FIELD = VAL' in given string.

  Args:
    data: String of data to search for.
    opt_ignore_duplicate: We have two options if we encounter a named field more
      than once: we can ignore the duplicate, or we can take the new value. By
      default, we will ignore the duplicate fields.
  Returns:
    Dictionaries 'field': 'val' where 'val' has been cast to float. NB: unless
    specified, only the first field found is specified.
  """
  # Extract the fields from the data.
  fields = {}
  for field in FIELDS_RE.findall(data):
    name, val = field.split('=')
    name = name.strip().upper()
    # Take the FRIST values seen.
    if not opt_ignore_duplicate or name not in fields:
      fields[name] = float(val.strip())
  return fields


def _SeparateSegments(num_segments, fields, data):
  """Pulls the segments out of the data.

  Depending on if the srcmod file is a multi or single segment file, this
  function will find the segment separator, and return the separated segment
  data.

  A single segment file looks like:

    % SRCMOD HEADER
    % SOURCE MODEL PARAMETERS
    %     [ SEGMENT_HEADER ]
    data

  A multi-segment file will look like:

    % SRCMOD HEADER
    % SEGMENT
    %     [ SEGMENT_HEADER ]
    data

    [.... num_segments ....]

    % SEGMENT
    %     [ SEGMENT_HEADER ]
    data

  Args:
    num_segments: The number of segments in the data.
    fields: The header of the srcmod file.
    data: The data (as a string) of the srcmod file.

  Returns:
    Tuple of (segments, segment_fields)
      segments: Array of all the segment data (as strings).
      segment_fields: The fields that have been stripped from the segment
        headers.
  """
  # Set up the segment data.
  if num_segments > 1:
    delimeter = '% SEGMENT'
    assert delimeter in data
    segments = [delimeter + _ for _ in data.split(delimeter)[1:]]
    segment_fields = [_FindFields(seg) for seg in segments]
  else:
    delimeter = '% SOURCE MODEL PARAMETERS'
    assert delimeter in data
    segments = [delimeter + _ for _ in data.split(delimeter)[1:]]
    segment_fields = [fields]
  assert len(segments) == num_segments
  assert len(segment_fields) == num_segments
  return segments, segment_fields


def _GetSegmentData(data):
  """Given a segment of data, we parse it into the appropriate fields.

  Args:
    data: String that contains all the characters in a segment's worth of data.
  Returns:
    List of lists of dictionaries.
  """
  ret = []
  rows = []
  names = []
  last_z = None
  for line in data.split('\n'):
    if not line: continue  # Skip blank lines
    if DATA_FIELDS_RE.match(line):  # Find field names
      # We extract the names of the fields.
      # The field names will be a in a string of the following form:
      #
      #     '%     F1   F2    F3==X     Z'
      #
      # First we split up the string by removing all spaces, discard the first
      # one ('%'), and then we remove any pieces after and including '=' in the
      # field name. NB: The last row must be a 'Z'
      names = [x.upper() for x in line.split()[1:]]
      names = [x.split('=')[0] if '=' in x else x for x in names]
    if line[0] == '%':  # Skip comment lines.
      continue
    else:
      # Make a dict of our values.
      val = {n: float(v) for n, v in zip(names, line.split())}
      assert -180. <= val['LON'] <= 180.
      assert -90. <= val['LAT'] <= 90.

      # If the z value we've just read in doesn't equal the last z value we've
      # read in, we have a new row. We then save off the row we've read so far
      # before adding the new value to the rows.
      if last_z is not None and val['Z'] != last_z:
        ret.append(rows)
        assert len(ret[0]) == len(ret[-1])  # Is same length as previous?
        rows = []
      rows.append(val)
      last_z = val['Z']
  if rows:
    ret.append(rows)
  assert len(ret[0]) == len(ret[-1])  # Is same length as previous?
  return ret


def ReadSrcmodFile(filename):
  """Reads a Srcmod file.

  Args:
    filename: Full path to Srcmod file.
  Returns:
    List of dictionaries. Each dictionary is a single segment of the fault.
  """
  logging.info('Reading SRCMOD file: %s', filename)

  src_mod = collections.defaultdict(list)
  with gcs.File(filename) as f:
    data = f.read()
    # Read the date.
    date = DATE_RE.search(data).group(0)
    src_mod['date'] = date
    src_mod['datetime'] = datetime.datetime.strptime(date, '%m/%d/%Y')

    # Extract tags
    tags = {}
    for tag in TAGS_RE.findall(data):
      name, val = tag.split(':')
      tags[name.strip().upper()] = val.strip()

    # Remap tags to src_mod output.
    for in_name, out_name in TAG_MAP:
      if in_name not in tags:
        print 'error', in_name, tags
        continue
      src_mod[out_name] = tags[in_name]

    # Find fields, and remap them to src_mod output.
    fields = _FindFields(data)
    for in_name, out_name in FIELD_MAP:
      if in_name not in fields:
        print 'error', in_name, fields
        continue
      src_mod[out_name] = fields[in_name]

    # Calculate some epicenter projection stuff.
    _, _, number, letter = utm.from_latlon(src_mod['epicenterLatitude'],
                                           src_mod['epicenterLongitude'])
    src_mod['zoneNumber'] = number
    src_mod['zoneLetter'] = letter
    proj = pyproj.Proj(proj='utm', zone='{}{}'.format(number, letter),
                       ellps='WGS84')
    src_mod['projEpicenter'] = proj
    src_mod['epicenterXUtm'], src_mod['epicenterYUtm'] = proj(
        src_mod['epicenterLongitude'], src_mod['epicenterLatitude'])

    # Set up the segment data.
    num_segments = int(fields['NSG'])
    segments, segment_fields = _SeparateSegments(num_segments, fields, data)

    # Loop through the segments.
    for i in range(num_segments):
      if segment_fields[i].has_key('STRIKE'):
        seg_strike = segment_fields[i]['STRIKE']
      else:
        seg_strike = fields['STRK']
      angle = -(seg_strike-90)
      if angle < 0:
        angle += 360

      data = _GetSegmentData(segments[i])
      if len(data) == 1: continue  # Skip short segments.

      # Calculate the length and wide if individual patch elements in current
      # panel.
      length = segment_fields[i].get('DX', fields['DX'])
      if segment_fields[i].has_key('LEN'):
        width = segment_fields[i]['LEN'] / len(data)
      else:
        width = fields['DZ']

      # Calculate the geometric coordinates of the segments.
      #
      # In the following code, we convert the srcmod data into a format we use
      # for our coloumb stress calculations. Specifically, we take the srcmod
      # data and remap the geometry into a form we need. The original srcmod
      # data looks like:
      #
      #               v this coordinate is the x,y,z data point.
      #       +-------*--------+
      #       |                |
      #       |                |
      #       +----------------+
      #
      # The original srcmod data is also along a x,y,z coordinate system where
      # the Z vector is projected from the core of the earth. We need to
      # decompse the data (using the strikeslip and dipslip[*]) of the fault.
      #
      # The first thing we do is find the offsets between the x/y coordinates --
      # specifically, [xy]_top_offset and [xyz]_top_bottom_offset. We calculate
      # these values as follows:
      #
      #   [xy]_top_offset is calculated by assuming the fault patches are
      #     uniformally spaced, and sized on a given segment. Given this, and
      #     the length and angle of the fault, we calculate the offsets as the
      #     length rotated about the angle.
      #   [xyz]_top_bottom_offsets are calculated by (again assuming uniform
      #     patch size) taking the difference between two [xyz] coordinates.
      #
      # We remap the coordinates into the following format:
      #
      #       <---------------->  x_top_offset * 2
      #       |                |
      #
      # xyz1  +----------------+ xyz2  --^
      #       |                |         |  x_top_bottom_offset
      #       |                |         |
      # xyz3  +----------------+ xyz4  --v
      #
      # We do this remaping with a number of different transforms for x, y, and
      # z.
      #
      # [*] strikeslip is the angle the fault, and slip as the two plates move
      # laterally across each other. dipslip is the angle of the fault as the
      # two plates move under/over each other.
      rot = np.array([[math.cos(math.radians(angle)),
                       -math.sin(math.radians(angle))],
                      [math.sin(math.radians(angle)),
                       math.cos(math.radians(angle))]])
      x_orig = np.array([[length / 2.0], [0.0]])
      x_rot = np.dot(rot, x_orig)
      x_top_offset = x_rot[0] * KM2M
      y_top_offset = x_rot[1] * KM2M
      x_top_bottom_offset = (data[1][0]['X'] - data[0][0]['X']) * KM2M
      y_top_bottom_offset = (data[1][0]['Y'] - data[0][0]['Y']) * KM2M
      z_top_bottom_offset = (data[1][0]['Z'] - data[0][0]['Z']) * KM2M

      # Loops over the down-dip and along-strike patches of the current panel
      for dip in range(0, len(data)):
        for strike in range(0, len(data[0])):
          # Extract top center coordinates of current patch
          x_top_center = data[dip][strike]['X'] * KM2M
          y_top_center = data[dip][strike]['Y'] * KM2M
          z_top_center = data[dip][strike]['Z'] * KM2M
          src_mod['patchLongitude'].append(data[dip][strike]['LON'])
          src_mod['patchLatitude'].append(data[dip][strike]['LAT'])

          # Calculate location of top corners and convert from km to m
          src_mod['x1'].append(x_top_center + x_top_offset)
          src_mod['y1'].append(y_top_center + y_top_offset)
          src_mod['z1'].append(z_top_center)
          src_mod['x2'].append(x_top_center - x_top_offset)
          src_mod['y2'].append(y_top_center - y_top_offset)
          src_mod['z2'].append(z_top_center)

          # Calculate location of bottom corners and convert from km to m
          src_mod['x3'].append(x_top_center + x_top_bottom_offset +
                               x_top_offset)
          src_mod['y3'].append(y_top_center + y_top_bottom_offset +
                               y_top_offset)
          src_mod['z3'].append(z_top_center + z_top_bottom_offset)
          src_mod['x4'].append(x_top_center + x_top_bottom_offset -
                               x_top_offset)
          src_mod['y4'].append(y_top_center + y_top_bottom_offset -
                               y_top_offset)
          src_mod['z4'].append(z_top_center + z_top_bottom_offset)

          # Create UTM version of the same
          x_top_center_utm, y_top_center_utm = proj(
              src_mod['patchLongitude'][-1], src_mod['patchLatitude'][-1])
          src_mod['patchXUtm'] = x_top_center_utm
          src_mod['patchYUtm'] = y_top_center_utm
          src_mod['x1Utm'].append(x_top_center_utm + x_top_offset)
          src_mod['y1Utm'].append(y_top_center_utm + y_top_offset)
          src_mod['z1Utm'].append(z_top_center)
          src_mod['x2Utm'].append(x_top_center_utm - x_top_offset)
          src_mod['y2Utm'].append(y_top_center_utm - y_top_offset)
          src_mod['z2Utm'].append(z_top_center)
          src_mod['x3Utm'].append(x_top_center_utm + (x_top_bottom_offset +
                                                      x_top_offset))
          src_mod['y3Utm'].append(y_top_center_utm + (y_top_bottom_offset +
                                                      y_top_offset))
          src_mod['z3Utm'].append(z_top_center + z_top_bottom_offset)
          src_mod['x4Utm'].append(x_top_center_utm + (x_top_bottom_offset -
                                                      x_top_offset))
          src_mod['y4Utm'].append(y_top_center_utm + (y_top_bottom_offset -
                                                      y_top_offset))
          src_mod['z4Utm'].append(z_top_center + z_top_bottom_offset)

          # Extract patch dip, strike, width, and length
          # NB: dipMean and strikeMean are not length weighted
          src_mod['dip'].append(segment_fields[i]['DIP'])
          src_mod['strike'].append(seg_strike)
          src_mod['dipMean'] = np.mean(np.array(src_mod['dip']))
          src_mod['strikeMean'] = np.mean(np.array(src_mod['strike']))
          src_mod['rake'].append(data[dip][strike].get('RAKE', 0))
          src_mod['angle'].append(angle)
          src_mod['width'].append(KM2M * width)
          src_mod['length'].append(KM2M * length)

          # Extract fault slip
          src_mod['slip'].append(data[dip][strike]['SLIP'])
          rot = np.array([[math.cos(math.radians(src_mod['rake'][-1])),
                           -math.sin(math.radians(src_mod['rake'][-1]))],
                          [math.sin(math.radians(src_mod['rake'][-1])),
                           math.cos(math.radians(src_mod['rake'][-1]))]])
          x_orig = np.array([[src_mod['slip'][-1]], [0]])
          x_rot = np.dot(rot, x_orig)
          src_mod['slipStrike'].append(x_rot[0])
          src_mod['slipDip'].append(x_rot[1])

  # Check that our dips and strikes are within proper ranges.
  for dip in src_mod['dip']:
    assert -180. <= dip <= 180.
  for strike in src_mod['strike']:
    assert 0. <= strike <= 360.

  logging.info('Done reading SRCMOD file %s', filename)

  return src_mod
