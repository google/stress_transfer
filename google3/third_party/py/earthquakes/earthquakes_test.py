"""Tests for google3.third_party.py.earthquakes.earthquakes."""

from google3.testing.pybase import googletest
from google3.third_party.py.earthquakes import earthquakes


class EarthquakesTest(googletest.TestCase):

  def testFRange(self):
    self.assertEquals(len(list(earthquakes.FRange('50'))), 1)
    self.assertEquals(len(list(earthquakes.FRange('10:20:0.5'))), 20)
    self.assertEquals(len(list(earthquakes.FRange('10:20.1:0.5'))), 21)
    self.assertEquals(len(list(earthquakes.FRange('10:11:5'))), 1)
    self.assertEquals(len(list(earthquakes.FRange('10:10:0.5'))), 0)
    self.assertEquals(len(list(earthquakes.FRange('10:2:0.5'))), 0)


if __name__ == '__main__':
  googletest.main()
