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
"""Scheduler for all Srcmod tasks."""

import datetime
import json
import logging
import pickle

from flask import Flask
from flask import request, make_response

from google.appengine.ext import ndb

app = Flask(__name__)
app.config['DEBUG'] = True

# We consider a worker as abandoned, or crashed, if it hasn't pinged in this
# amount of time, and will reallocate the work.
TIMEOUT = datetime.timedelta(seconds=600)

# Used to reset any times in our datastore.
LONG_TIME_AGO = datetime.datetime(1, 1, 1)

# The name of the bucket to store results.
BUCKET = 'clouddfe-cfs'

# The valid URL parameters when someone tries to add work.
VALID_PARAMS = [
    'srcmod',
    'coefficient_of_friction',
    'mu_lambda_lame',
    'near_field_distance',
    'spacing_grid',
    'obs_depth',
    'days',
    'isc_catalog',
    'priority',
]


def GetKey(args):
  """Returns (preferentially) 'key' or 'id' form url parameters."""
  key = args.get('key')
  if key: return key
  return args.get('id')


class RunStatus(ndb.Model):
  """Data packet for a run."""
  date = ndb.DateTimeProperty(auto_now_add=True)

  # Parameters
  parameters = ndb.StringProperty()
  parameter_filename = ndb.StringProperty()
  parameter_coefficient_of_friction = ndb.StringProperty()
  parameter_mu_lambda_lame = ndb.StringProperty()
  parameter_near_field_distance = ndb.StringProperty()
  parameter_spacing_grid = ndb.StringProperty()
  parameter_obs_depth = ndb.StringProperty()
  parameter_days = ndb.StringProperty()
  parameter_catalog_type = ndb.StringProperty()
  parameter_priority = ndb.StringProperty()

  # Status.
  is_completed = ndb.BooleanProperty(default=False)
  checkin_count = ndb.IntegerProperty(default=0)  # Used for transactions.
  last_runner_checkin = ndb.DateTimeProperty(default=LONG_TIME_AGO)
  uuid = ndb.StringProperty()
  high_priority = ndb.BooleanProperty(default=False)  # Used to boost execution.

  # Error conditions.
  # Note we store the errors in two fields, "errors" and "full_errors". We do it
  # this way because StringProperty is limited to 1500 characters, and
  # TextProperty isn't searchable. So, that's a thing.
  can_retry = ndb.ComputedProperty(lambda self: len(self.errors) < 3)
  num_errors = ndb.ComputedProperty(lambda self: len(self.errors))
  errors = ndb.StringProperty(repeated=True)  # Used for computed properties.
  full_errors = ndb.TextProperty(repeated=True)

  def SaveParameters(self, parameters):
    """Saves the paramters of a new run off.

    Arguments:
      parameters: String or list of the new parmaeters.
    """
    if type(parameters) == list:
      self.parameters = json.dumps(parameters)
    else:
      self.parameters = parameters
      parameters = json.loads(parameters)
    parameters = [str(p) for p in parameters]
    self.parameter_filename = parameters[0]
    self.parameter_coefficient_of_friction = parameters[1]
    self.parameter_mu_lambda_lame = parameters[2]
    self.parameter_near_field_distance = parameters[3]
    self.parameter_spacing_grid = parameters[4]
    self.parameter_obs_depth = parameters[5]
    self.parameter_days = parameters[6]
    self.parameter_catalog_type = parameters[7]
    self.parameter_priority = parameters[8]
    self.high_priority = (int(self.parameter_priority) != 0)
    self.put()

  @ndb.transactional(retries=0)
  def Checkin(self, uuid):
    """Checkin that we've be run lately."""
    logging.info('checking in')
    # Check the UUIDs. If they aren't the same, we need to check the time.
    if self.uuid and uuid != self.uuid:
      logging.info('uuids don\'t match %s %s', uuid, self.uuid)
      if self.last_runner_checkin + TIMEOUT > datetime.datetime.now():
        logging.info(self.last_runner_checkin)
        raise RuntimeError
    self.uuid = uuid
    self.checkin_count += 1
    self.last_runner_checkin = datetime.datetime.now()
    self.put()

  def Restart(self):
    """Marks a run as needing to be restarted."""
    self.is_completed = False
    self.checkin_count = 0
    self.last_runner_checkin = LONG_TIME_AGO
    self.errors = []
    self.full_errors = []
    self.put()

  def Filename(self):
    """Returns a filename for this run."""
    return '{}_{num:08.1f}'.format(self.parameter_filename[1:],
                                   num=float(self.parameter_obs_depth))

  def CompletedURL(self):
    """Returns URL to all completed results."""
    return '/scheduler/completed?srcmod={}'.format(self.parameter_filename)

  def CompletedJSONURL(self):
    """Returns URL to JSON completed results."""
    return '{}&json'.format(self.CompletedURL())

  def URLForResults(self):
    """Returns the URL for the results data."""
    return '/scheduler/results/{}'.format(self.Filename())

  def HTMLStatus(self):
    errors = self.full_errors
    if len(self.errors) > len(self.full_errors):
      errors = self.errors
    e = '<hr>'.join([_.replace('\n', '<br>') for _ in errors])
    ret = """
      id {} <br>
      parameters {} <br>
      is_completed {} <br>
      high_priority {} <br>
      last_runner_checkin {} <br>
      num_errors {} <br>
      errors <br> {} <br>
      <hr>
    """.format(self.key.id(), self.parameters, self.is_completed,
               self.high_priority, self.last_runner_checkin, self.num_errors, e)
    return ret

  def DictStatus(self):
    """Get the status of a run as a dict."""
    return {
        'id': self.key.id(),
        'key': self.key.id(),
        'is_completed': self.is_completed,
        'parameters': self.parameters,
        'num_errors': self.num_errors,
    }


def GetWorkStatus():
  """Returns an HTML string of the current worker status."""
  # TODO(jfaller): These queries should likely be STRONG_CONSISTENCY.
  total = RunStatus.query()
  running = RunStatus.query(RunStatus.last_runner_checkin >=
                            datetime.datetime.now() - TIMEOUT,
                            RunStatus.is_completed == False)
  completed = RunStatus.query(RunStatus.is_completed == True)
  in_error = RunStatus.query(RunStatus.num_errors > 0)
  completed_with_errors = RunStatus.query(RunStatus.num_errors > 0,
                                          RunStatus.is_completed == True)
  completed_high = RunStatus.query(RunStatus.is_completed == True,
                                   RunStatus.high_priority == True)
  todo_high = RunStatus.query(RunStatus.is_completed == False,
                              RunStatus.high_priority == True)
  ret = """
    total {} <br>
    running {} <br>
    completed {} <br>
    todo_high {} <br>
    completed_high {} <br>
    <hr>
    with_errors {} <br>
    completed_with_errors {} <br>
  """.format(total.count(), running.count(), completed.count(),
             todo_high.count(), completed_high.count(), in_error.count(),
             completed_with_errors.count())
  return ret


def AddWork():
  """Adds work to the queue."""
  for arg in request.args:
    if arg not in VALID_PARAMS:
      return 'Invalid argument {}'.format(arg), 400

  parameters = []
  parameters.append(request.args.get('srcmod', 's1968TOKACH01NAGA.fsp'))
  parameters.append(float(request.args.get('coefficient_of_friction', 0.4)))
  parameters.append(float(request.args.get('mu_lambda_lame', 3e10)))
  parameters.append(float(request.args.get('near_field_distance', 100e3)))
  parameters.append(float(request.args.get('spacing_grid', 10e3)))
  parameters.append(float(request.args.get('obs_depth', -10e3)))
  parameters.append(float(request.args.get('days', 100)))
  parameters.append(request.args.get('isc_catalog', 'rev'))
  parameters.append(int(request.args.get('priority', 0)))
  parameters = json.dumps(parameters)
  if RunStatus.query(RunStatus.parameters == parameters).count():
    logging.info('trying to add work that already exists.')
    return 'Trying to add work that already exists.', 400
  work = RunStatus()
  work.SaveParameters(parameters)
  work.put()
  return GetWorkStatus()


def RequestWork():
  """API for worker threads to request a work packet."""
  # Check for work that's not completed and hasn't been pinged in a while.
  run = RunStatus.query(RunStatus.is_completed == False,
                        RunStatus.can_retry == True,
                        RunStatus.high_priority == True,
                        RunStatus.last_runner_checkin < datetime.datetime.now()
                        - TIMEOUT).get()
  if not run:
    run = RunStatus.query(RunStatus.is_completed == False,
                          RunStatus.can_retry == True,
                          RunStatus.last_runner_checkin <
                          datetime.datetime.now() - TIMEOUT).get()
  if not run:
    return 'Nothing to run', 204
  logging.info('Work requested. Returning: %d', run.key.id())
  try:
    run.Checkin(request.args.get('uuid'))
  except:
    logging.info('Collided on key: %d', run.key.id())
    return 'Collision on key, try again', 500
  return json.dumps({
      'id': run.key.id(),
      'key': run.key.id(),
      'parameters': run.parameters,
  })


def Checkin():
  """Register a checkin from a worker thread."""
  key = GetKey(request.args)
  if not key:
    return 'No valid key specified', 400
  logging.info('Checking id %s     %d', key, int(key))
  run = RunStatus.get_by_id(int(key))
  if not run:
    return 'No object found', 404
  try:
    run.Checkin(request.args.get('uuid'))
  except:
    logging.info('Failed to checkin %s', request.args.get('uuid'))
    return 'Collision on key, try again', 500
  return run.uuid


def GetStatus():
  """Get the status of all work in flight."""
  status = GetWorkStatus()
  key = GetKey(request.args)
  if not key:
    return status
  run = RunStatus.get_by_id(int(key))
  if not run:
    ret = '<B>Invalid key</b><br>'
  else:
    ret = run.HTMLStatus()
  return ret + status


def ReportError():
  """Reports an error."""
  key = GetKey(request.args)
  if not key:
    logging.info('no key')
    return 'Must specify key', 400
  run = RunStatus.get_by_id(int(key))
  if not run:
    logging.info('no run %d', key)
    return 'Must specify valid key', 404
  if run.is_completed:
    logging.info('run was completed but error uploaded %d', key)
    return 'Run was already completed??', 400
  if not request.form.has_key('error'):
    logging.info('no stack trace given')
    return 'No stacktrace given in <i>error</i> field.', 400
  error = request.form['error']
  run.full_errors.append(error)
  if len(error) > 1500:
    error = error[:1500]
  run.errors.append(error)
  run.last_runner_checkin = LONG_TIME_AGO
  run.put()
  return 'Run {} has {} errors'.format(key, run.num_errors)


def UploadResult():
  """Accepts an uploaded result."""
  key = GetKey(request.args)
  if not key:
    logging.info('no key')
    return 'Must specify key or id', 400
  run = RunStatus.get_by_id(int(key))
  if not run:
    logging.info('no run')
    return 'Must specify valid key', 404
  run.last_runner_checkin = LONG_TIME_AGO
  run.is_completed = True
  run.put()
  return 'Successfully updated image {}'.format(key)


def RestartRun(key):
  """Accepts an uploaded result."""
  run = RunStatus.get_by_id(int(key))
  if not run:
    logging.info('no run')
    return 'Must specify valid key', 404
  run.Restart()
  return '{} restarted'.format(int(key))


def GetCompleted():
  """Gets the completed results."""
  key = GetKey(request.args)
  srcmod = request.args.get('srcmod', None)
  q = None
  if key:  # Get by key/id.
    q = [RunStatus.get_by_id(int(key))]
  if not q and srcmod:  # Get by srcmod.
    q = RunStatus.query(RunStatus.parameter_filename == srcmod,
                        RunStatus.is_completed == True)
  if not q:  # If no query parameters, just get completed.
    q = RunStatus.query(projection=[RunStatus.parameter_filename],
                        distinct=True)
    if request.args.has_key('json'):
      return json.dumps([{run.parameter_filename: run.CompletedJSONURL()}
                         for run in q])
    return '<BR>'.join([('<B>{}</B> '
                         '<A HREF="{}">RESULTS</A> '
                         '<A HREF="{}">JSON</A>'.format(run.parameter_filename,
                                                        run.CompletedURL(),
                                                        run.CompletedJSONURL()))
                        for run in q])
  if request.args.has_key('json'):  # Send JSON data?
    return json.dumps([run.DictStatus() for run in q])
  return '<HR>'.join([run.HTMLStatus() for run in q])

