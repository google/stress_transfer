"""isc.py tests."""

import collections
from datetime import datetime
import time

import google3

from earthquakes.isc import isc

from google3.testing.pybase import googletest


PATH = 'google3/third_party/py/earthquakes/isc/test_data.csv'


class FileIoTest(googletest.TestCase):

  def _GetRawData(self, t=time.gmtime()):
    """Returns a raw row like it was CSV parsed."""
    row = collections.defaultdict(str)
    row['author'] = 'ISC'
    row['date_time'] = time.strftime('%Y-%m-%d %H:%M:%S.1234', t)
    row['lat'] = '10.25'
    row['lon'] = '20.25'
    row['major_axis'] = '55'
    row['minor_axis'] = '65'
    row['strike'] = '245'
    row['depth'] = '75'  # This row should be positive for testing!
    row['depfixflag'] = 'G'
    row['depth_uncertainty'] = '0.0'
    row['magnitude_author'] = isc.VALID_MAGNITUDE_TYPES[0]
    row['magnitude'] = '5.5'
    row['magnitude_type'] = 'MW'
    row['stations'] = '5'
    row['event_type'] = 'ke'
    row['event_id'] = '1'
    return row

  def _GetConvertedData(self, t=time.gmtime()):
    """Returns a good row, as though it's been CSV parsed, and converted."""
    row = self._GetRawData(t)
    isc._ConvertTypes(row)
    return row

  def testEmptyMagnitudeAuthor(self):
    """Test that if a field has an empty magnitude author it gets stripped."""
    row = self._GetConvertedData()
    self.assertTrue(isc._IsRowValid(row))
    row['magnitude_author'] = ''
    self.assertFalse(isc._IsRowValid(row))

  def testBadMagnitudeType(self):
    """Test if a bad magnitude type gets stripped."""
    row = self._GetConvertedData()
    self.assertTrue(isc._IsRowValid(row))
    row = self._GetRawData()
    row['magnitude_type'] = 'BOGUS'
    isc._ConvertTypes(row)
    self.assertFalse(isc._IsRowValid(row))

  def testNoMagnitude(self):
    """Test if there's no magnitude it gets stripped."""
    row = self._GetConvertedData()
    self.assertTrue(isc._IsRowValid(row))
    row = self._GetRawData()
    row['magnitude'] = ''
    isc._ConvertTypes(row)
    self.assertFalse(isc._IsRowValid(row))

  def testTypeConversion(self):
    """Test if we convert all types correctly."""
    row = self._GetConvertedData()
    for field in isc.FLOAT_FIELDS:
      self.assertEquals(type(row[field]), float)
    for field in isc.INT_FIELDS:
      self.assertEquals(type(row[field]), int)
    self.assertTrue(row['depth'] < 0)

  def testUtmConversionPossible(self):
    row = self._GetConvertedData()
    self.assertTrue(isc._IsRowValid(row))
    row['lat'] = 84
    self.assertTrue(isc._IsRowValid(row))
    row['lat'] = -80
    self.assertTrue(isc._IsRowValid(row))
    row['lat'] = 84.001
    self.assertFalse(isc._IsRowValid(row))
    row['lat'] = -80.001
    self.assertFalse(isc._IsRowValid(row))

  def testYearRange(self):
    start = datetime(1, 1, 1)
    self.assertEquals(sum([1 for _ in isc._YearRange(start, 10)]), 1)
    self.assertEquals(sum([1 for _ in isc._YearRange(start, 364)]), 1)
    self.assertEquals(sum([1 for _ in isc._YearRange(start, 365)]), 2)
    start = datetime(25, 12, 1)  # XMAS
    self.assertEquals(sum([1 for _ in isc._YearRange(start, 1)]), 1)
    self.assertEquals(sum([1 for _ in isc._YearRange(start, 7)]), 1)


if __name__ == '__main__':
  googletest.main()
