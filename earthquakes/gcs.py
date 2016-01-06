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
"""Functions to interact with Google Cloud Storage."""

import io
import logging
import os
import StringIO
import tempfile

from apiclient import discovery
from apiclient.errors import HttpError
from apiclient.http import MediaIoBaseDownload
import httplib2
from oauth2client.client import GoogleCredentials


# Size of the data to download from GCE at a chunk.
CHUNK_SIZE = 2 * 1024 * 1024

# Retry transport and file IO errors.
RETRYABLE_ERRORS = (httplib2.HttpLib2Error, IOError)


def File(gs_path, chunk_size=CHUNK_SIZE):
  """Download a file from the cloud, and return a file that's readable.

  Args:
    gs_path: Fully qualified gfs path, eg, 'gfs://bucket/path/to/FILE'.
    chunk_size: The chunk_size to download, defaults to CHUNK_SIZE.

  Returns:
    An IO stream to be read.
  """
  bucket_name, object_name = gs_path[5:].split('/', 1)
  logging.info('Downloading file: %s/%s', bucket_name, object_name)

  credentials = GoogleCredentials.get_application_default()
  service = discovery.build('storage', 'v1', credentials=credentials)
  request = service.objects().get_media(bucket=bucket_name, object=object_name)
  output = StringIO.StringIO()
  media = MediaIoBaseDownload(output, request, chunksize=chunk_size)
  done = False
  while not done:
    try:
      _, done = media.next_chunk()
    except HttpError, err:
      if err.resp.status < 500:
        raise
    except RETRYABLE_ERRORS, err:
      pass
  logging.info('Downloaded file: %s/%s', bucket_name, object_name)
  return io.BytesIO(output.getvalue())


def Write(gs_path, data, suffix='.txt'):
  """Writes data to the cloud."""
  credentials = GoogleCredentials.get_application_default()
  service = discovery.build('storage', 'v1', credentials=credentials)

  bucket_name, object_name = gs_path[5:].split('/', 1)
  logging.info('Uploading file: %s/%s', bucket_name, object_name)

  # Save the data off into a temp file.
  tfile = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
  tfile.write(data)
  tfile.close()

  # Upload the data.
  logging.info('filename: %s   %s     %s', tfile.name, object_name, bucket_name)
  req = service.objects().insert(media_body=tfile.name, name=object_name,
                                 bucket=bucket_name)
  _ = req.execute()

  # Cleanup.
  os.remove(tfile.name)
