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
"""Simple that runs the Coloumb Stress code."""

import cStringIO
import json
import logging
from optparse import OptionParser
import os
import pickle
import sys
import threading
import time
import traceback
import uuid

import gcs
import ProcessSrcmod as process
import requests

BUCKET = 'clouddfe-cfs'
SRCMOD = 'gs://{}/srcmod'.format(BUCKET)
UUID = str(uuid.uuid1())

# Should the status thread run?
should_status = True

# Set up command line parser.
parser = OptionParser()
parser.add_option('-j', '--jobs', dest='jobs', default=1,
                  help='Number of processes to spin up.')
parser.add_option('-p', '--parameters', dest='parameters', default=None,
                  help='Parameters with which to run the app.')
parser.add_option('-i', '--id', dest='id',
                  default='LOCAL {}'.format(time.asctime()),
                  help='ID/filename to use for files on runs with parameters.')
parser.add_option('-h', '--host', dest='host',
                  default='http://shaky-foundation-02138.appspot.com/',
                  help='AppEngine hostname that\'s running the scheduler.')


def Filename(parameters):
  """Returns the base filename for a given set of parameters."""
  return '{}_{num:08.1f}'.format(parameters[0][1:],
                                 num=float(parameters[5]))


def GetImageFileNameOnCloud(parameters):
  """Given the parameters of the run, returns the full image filename."""
  return 'gs://{}/graphs/{}'.format(BUCKET, Filename(parameters))


def GetResultFileNameOnCloud(parameters):
  """Given the parameters of the run, returns the full results filename."""
  return 'gs://{}/results/{}.txt'.format(BUCKET, Filename(parameters))


def RequestWork(host, retries=10):
  """Requests work from the scheduler.

  Arguments:
    retries: Number of times to retry requesting work.
  Returns:
    Dictionary of work values.
  """
  url = host + '/scheduler/request_work'
  logging.info('Requesting work %s', url)
  while True:
    if retries < 0:
      logging.info('Ran out of retries.')
      return None
    response = requests.get(url, params={'uuid': UUID})
    if response.status_code != requests.codes.ok:
      time.sleep(5)  # backoff a little bit.
      logging.info('Error: %d', response.status_code)
      retries -= 1
      continue
    ret = json.loads(response.text)
    time.sleep(5)  # back off a little bit
    if not Checkin(ret['id']):
      time.sleep(5)  # back off a little bit
      logging.info('Checkin failed')
      retries -= 1
      continue
    break
  logging.info('Work receivced "%s"', response.text)
  return ret


def ReportResults(host, key):
  """Reports results to appengine scheduler.

  Arguments:
    host: The host to connect to.
    key: What key to send results to.
  """
  url = host + '/scheduler/upload'
  logging.info('Sending (%d) results %s', key, url)
  r = requests.post(url, params={'key': key})
  if r.status_code != requests.codes.ok:
    logging.error('Error %d sending results for work %d', r.status_code, key)
    return
  logging.info('successfully uploaded %s', key)


def ReportError(host, key, error):
  """Reports an error to the server.

  Arguments:
    host: The host to connect to.
    key: The key to report error to.
    error: Error string (stack trace) to report.
  """
  url = host + '/scheduler/error'
  r = requests.post(url, data={'error': error}, params={'key': key})
  if r.status_code != requests.codes.ok:
    logging.error('Error (%d) reporting error\n %s', r.status_code, error)
    return
  logging.info('Error reported for key(%d)', key)


def Checkin(key):
  """Checkin once.

  Args:
    key: The UUID (as a String) of the run we're checking in.

  Returns:
    True/False if the checkin was successful.
  """
  url = host + '/scheduler/checkin'
  r = requests.get(url, params={'key': key, 'uuid': UUID})
  if r.status_code != requests.codes.ok:
    return False
  return r.text == UUID



def ReportStatus(host, key, interval):
  """Ping the server, reporting living status.

  Continuously pings the server saying, "this UUID is alive and still
  processing," so that the work packet doesn't get scheduled with a different
  worker. To kill this thread, set the global "should_status" to False.

  Args:
    host: The host to connect to.
    key: The UUID (as a string) for which we should ping as "alive".
    interval: Time in seconds between pings.
  """
  global should_status
  logging.info('Starting ping thread')
  while should_status:
    logging.info('Pinging server for id %d', key)
    if not Checkin(host, key):
      logging.info('Failed to checkin.')
      return
    for _ in range(interval):
      time.sleep(1)
      if not should_status:
        return
  logging.info('DONE pinging server for id %d', key)


def main(_=None):
  global should_status

  # Parse the command line options.
  (options, _) = parser.parse_args()
  run_local = (options.parameters is not None)
  if not run_local:
    # Start '-jobs' works -- each in a different process so they get their own
    # CPU, memory space, etc.
    for i in range(1, int(options.jobs)):
      if os.fork():
        logging.info('Spawned job %d', i)
      else:  # In child.
        break

  while True:
    # If we're a local run, we have the parameters. Format them like we got them
    # from appengine. Otherwise, we grab our work packet from the web.
    if run_local:
      logging.info('Running locally %s', options.parameters)
      work = {
          'id': options.id,
          'parameters': options.parameters,
      }
    else:
      # Grab work packet from the web.
      work = RequestWork(options.host)
    if not work:
      logging.info('No Work')
      break
    try:
      key = work['id']

      if not run_local:
        # Start pinging the server.
        should_status = True
        status_thread = threading.Thread(target=ReportStatus,
                                         args=(options.host, key, 240))
        status_thread.start()

      # Get everything into place for processing.
      logging.info('starting quake')
      logging.info(work)
      parameters = json.loads(work['parameters'])
      results_filename = GetResultFileNameOnCloud(parameters)
      image_filename = GetImageFileNameOnCloud(parameters)
      parameters[0] = os.path.join(SRCMOD, parameters[0])

      # Run the quake.
      criteria, graph = process.ModelQuake(*parameters[:8])

      logging.info('done quake')

      # Output the data.
      if graph:  # If we have graph data, send it to the cloud.
        gcs.Write(image_filename, graph, suffix='.png')
      else:
        logging.error('******** No graph generated!!!!!!!!!')

      # Write the CFS data.
      logging.info('size: %d', sys.getsizeof(criteria))
      gcs.Write(results_filename, pickle.dumps(criteria))
      if not run_local:
        ReportResults(options.host, key)

    except:
      # Uh-oh. We've had an exception. Capture it, and report it.
      logging.info('Fatal error, stopping run')
      f = cStringIO.StringIO()
      traceback.print_exc(file=f)
      stack = f.getvalue()
      if not run_local:
        ReportError(options.host, key, stack)
      logging.error('EXCEPTION. Stack trace\n%s', stack)

    finally:
      # Stop pinging the server.
      logging.info('stopping reporter')
      should_status = False
      if not run_local and status_thread:
        status_thread.join()

    # If we're a local run, break out.
    if run_local: break

    logging.info('Done work')
  logging.info('SHUTTING DOWN')


if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO)
  main(sys.argv)
