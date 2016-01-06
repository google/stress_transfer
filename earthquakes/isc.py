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
"""Earthquakes ISC file I/O functions.

Functions for reading in ISC earthquake data.
"""
import csv
import datetime
import logging
import operator
import os

import gcs
from geopy.distance import great_circle
from geopy.distance import vincenty

# This list of fields returned in a an ISC row.
FIELDS = [
    'author',
    'date_time',
    'lat',
    'lon',
    'major_axis',
    'minor_axis',
    'strike',
    'depth',
    'depfixflag',
    'depth_uncertainty',
    'magnitude_author',
    'magnitude',
    'magnitude_type',
    'stations',
    'event_type',
    'event_id',
]

# These magnitude types are the only types that are considered valid in the
# IsGoodRow function.
VALID_MAGNITUDE_TYPES = [
    'Mb',
    'mb',
    'ML',
    'Ml',
    'ml',
    'Mw',
    'MW',
    'Ms',
    'MS',
]

# When reading a CSV row, these fields are converted to floats.
FLOAT_FIELDS = [
    'lat',
    'lon',
    'major_axis',
    'minor_axis',
    'strike',
    'depth',
    'depth_uncertainty',
    'magnitude',
]

# These fields will be converted to int before being returned from the ISC
# reader.
INT_FIELDS = [
    'stations',
]

# Valid catalog types.
VALID_CATALOGS = [
    'comp',
    'ehb',
    'rev',
]

# Format of the datetime field in the CSV file.
# You'll note that there's a timezone here, and the csv files don't include TZ
# info. We add it before parsing the date, otherwise the datetime we generate is
# difficult to compare against.
DATE_FORMAT = '%Y-%m-%d %H:%M:%S %Z'


def _ConvertTypes(row):
  """Modifies a row in CSV file to proper types for analysis.

  Args:
    row: dictionary of all elements in a row, which is modified in place.
  """
  # Convert date/time to a type -- but throwing away milliseconds.
  # Notice, that we also set the TZ to UTC to ensure is_dst doesn't mess with
  # us.
  d = row['date_time'].split('.')[0]
  row['date_time'] = datetime.datetime.strptime(d + ' UTC', DATE_FORMAT)

  # Convert number fields.
  for field in FLOAT_FIELDS:
    try:
      row[field] = float(row[field])
    except ValueError:
      pass  # Ignore conversion errors which are likely caused by empty fields.
  for field in INT_FIELDS:
    try:
      row[field] = int(row[field])
    except ValueError:
      pass  # Ignore conversion errors which are likely caused by empty fields.
  # ISC data has inconsistent signs for depth. We make sure they're all
  # consistently negative, like my outlook.
  if row.has_key('depth') and type(row['depth']) == float:
    row['depth'] = -1 * abs(row['depth'])


def _IsRowValid(row):
  """Is the data row considered good?

  Args:
    row: dictionary of the row in the ISC data.

  Returns:
    True if the data is considered good, and we should append it to the
    list of good data. Right now, a row is good if:
      * It contains a magnitude_author
      * magnitude_type is one of the valid types from VALID_MAGNITUDE_TYPES
      * the magnitude can be converted to a float.
  """
  # Skip data where the author wasn't proud enough to tag it as theirs.
  if not row['magnitude_author']: return False

  # Skip data where the the magnitude type makes no sense. (These values were
  # given in an e-mail from meadeb@.)
  if row['magnitude_type'] not in VALID_MAGNITUDE_TYPES: return False

  # Skip data where the magnitude isn't a number.
  if type(row['magnitude']) != float: return False

  #  Make sure we can convert the data to UTM coordinates.
  if row['lat'] > 84 or row['lat'] < -80: return False

  return True


def _ReadCsvFile(filename, data_validator):
  """Reads the specified ISC CSV file.

  Args:
    filename: path to the file you'd like to read.
    data_validator: Validation function that returns True/False if a row should
      be included in the returned rows.

  Returns:
    An array of dictionaries, where the field names are specified by FIELDS.
    Note that the fields in the dictionaries have been converted from strings to
    their representative types (ie, numbers, dates, or strings.)
  """
  logging.info('Reading ISC file: %s', filename)
  ret = []
  try:
    with gcs.File(filename) as csvfile:
      rows = csv.reader(csvfile)
      for row in rows:
        cols = [_.strip() for _ in row]
        assert len(cols) == len(FIELDS)
        d = {FIELDS[i]: cols[i].strip() for i in range(len(cols))}
        _ConvertTypes(d)
        if data_validator(d):
          ret.append(d)
  except:  # Error reading file, ignoring.
    logging.error('Error reading isc file %s', filename)
  return ret


def _ReadAndFilterData(filename, start_date, end_date, pos, distance):
  """Creates a filter function for the CSV reader, and reads csv data.

  Args:
    filename: The path of the file to read.
    start_date: Start date we should begin filtering the data.
    end_date: End date we should begin filtering the data.
    pos: Location we should be filtering the data for.
    distance: Distance in KM for which we include aftershocks.

  Returns:
    List of dictionaries of ISC data.
  """
  def _Filter(x):
    """Filter that we apply to all isc data."""
    try:
      # Remove the normal problems with the data.
      if not _IsRowValid(x): return False
      # Make sure the data point is in the date range specified.
      if not start_date <= x['date_time'] <= end_date: return False
      # Make sure the data point is within the distance specified.
      if vincenty((x['lat'], x['lon']), pos) > distance: return False
    except ValueError:
      # Vincenty doesn't always converge. If it fails to, then default to a
      # Great Circle distance.
      if great_circle((x['lat'], x['lon']), pos) > distance: return False
    return True
  return _ReadCsvFile(filename, data_validator=_Filter)


def _YearRange(start_date, days):
  """Generator that will loop through years given a start date and num days."""
  end_date = start_date + datetime.timedelta(days=days)
  for y in range(start_date.year, end_date.year + 1):
    yield y


def ReadISCData(gcs_path, catalog, start_date, days, pos, distance):
  """Reads the ISC data for a specified time, location, and distance.

  NB: This function will read multiple years worth of ISC files if necessary.

  Args:
    gcs_path: The fully qualified gcs path, eg 'gcs://bucket/path/to/isc/files'.
    catalog: One of 'comp', 'ehb', 'rev'.
    start_date: The date of the quake we care about, as a datetime.
    days: The number of days from "date" for which we want to find quakes.
    pos: The lat/long of the quake (as a tuple).
    distance: The max distance from lat/long from which to filter quakes.
  Raises:
    RuntimeError: If the catalog isn't in the set of valid catalogs.
  Returns:
    The filtered ISC data, sorted according to the date.
  """
  logging.info('Reading ISC data for date: %s, lat/lon %s, distance %d, and '
               'days: %d', str(start_date), str(pos), distance, days)
  if catalog not in VALID_CATALOGS:
    raise RuntimeError('Invalid catalog')
  end_date = start_date + datetime.timedelta(days=days)

  d = os.path.join(gcs_path, catalog + 'csv')
  ret = []
  # Loop through the different ISC files/years.
  for y in _YearRange(start_date, days):
    logging.info('Reading ISC data for year %d', y)
    path = os.path.join(d, '{}.csv'.format(y))
    ret += _ReadAndFilterData(path, start_date, end_date, pos, distance)
  ret.sort(key=operator.itemgetter('date_time'))
  return ret

