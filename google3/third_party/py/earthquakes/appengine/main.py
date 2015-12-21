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
"""Main server for appengine."""
import datetime
import json
import logging

from earthquakes import isc
from flask import Flask
from flask import request
import process
import utm

app = Flask(__name__)
app.config['DEBUG'] = True


DATE_FORMAT = '%Y-%m-%d:%H:%M'

# Add the scheduler rules.
app.add_url_rule('/scheduler/status', 'status', view_func=process.GetStatus)
app.add_url_rule('/scheduler/checkin', 'checkin', view_func=process.Checkin)
app.add_url_rule('/scheduler/request_work', 'request_work',
                 view_func=process.RequestWork)
app.add_url_rule('/scheduler/upload', 'upload', view_func=process.UploadResult,
                 methods=['POST'])
app.add_url_rule('/scheduler/error', 'error', view_func=process.ReportError,
                 methods=['POST'])
app.add_url_rule('/scheduler/add_work', 'add_work', view_func=process.AddWork)
app.add_url_rule('/scheduler/restart/<key>', 'restart',
                 view_func=process.RestartRun)
app.add_url_rule('/scheduler/completed', 'completed',
                 view_func=process.GetCompleted)


@app.route('/')
def hello():
  """Return a friendly HTTP greeting."""
  return 'Hello World!'


@app.route('/events')
def events():
  """Gets isc data."""
  missing_params = []
  for p in ['lat', 'lon', 'distance', 'start', 'end', 'mag', 'catalog']:
    if p not in request.args:
      missing_params.append(p)
  if missing_params:
    return 'Missing parameters: {}'.format(','.join(missing_params))

  start = datetime.datetime.strptime(request.args.get('start'),
                                     DATE_FORMAT)
  end = datetime.datetime.strptime(request.args.get('end'),
                                   DATE_FORMAT)
  time_delta = end - start
  logging.info('Start Time {}'.format(start))
  logging.info('End Time {}'.format(end))
  logging.info('Time Delta {}'.format(time_delta))

  # Read the isc data.
  isc_data = isc.ReadISCData('gs://clouddfe-cfs/isc',
                             request.args.get('catalog'),
                             start, abs(time_delta.days),
                             (long(request.args.get('lat')),
                              long(request.args.get('lon'))),
                             int(request.args.get('distance')))

  # Prepare the ISC data by:
  #   1) Filtering out magnitude events smaller than specified.
  #   2) Projecting the lat/lon to UTM.
  ret = []
  _, _, num, let = utm.from_latlon(float(request.args.get('lat')),
                                   float(request.args.get('lon')))
  proj = lambda lat, lon: utm.from_latlon(lat, lon, num)[0:2]
  mag = float(request.args.get('mag'))
  num_filtered = 0
  for data in isc_data:
    if data['magnitude'] < mag:
      num_filtered += 1
      continue
    x, y = proj(data['lat'], data['lon'])
    ret.append({
        'lat': data['lat'],
        'lon': data['lon'],
        'utm_x': x,
        'utm_y': y,
        'depth': data['depth'],
        'mag': data['magnitude'],
        'date': data['date_time'].isoformat(' '),  # YYYY-MM-DD HH:MM:SS
    })
  logging.info('Filtered (%d) ISC events due to magnitude', num_filtered)

  if 'callback' in request.args:
    return '{}({})'.format(request.args.get('callback'), json.dumps(ret))
  return json.dumps(ret)


@app.errorhandler(404)
def page_not_found(_):
  """Return a custom 404 error."""
  return 'Sorry, nothing at this URL.', 404
