"""Tests for Srcmod parser."""

import google3
from earthquakes.srcmod import srcmod
from google3.testing.pybase import googletest


class SrcmodTest(googletest.TestCase):

  def testFindFields(self):
    vals = srcmod._FindFields('FOO = 4')
    self.assertTrue(vals.has_key('FOO'))
    self.assertEquals(vals['FOO'], 4.)
    vals = srcmod._FindFields('FOO = -4.5e-6')
    self.assertTrue(vals.has_key('FOO'))
    self.assertEquals(vals['FOO'], -4.5e-6)
    vals = srcmod._FindFields('FOO = 1 FOO = 2')
    self.assertTrue(vals.has_key('FOO'))
    self.assertEquals(vals['FOO'], 1.)
    vals = srcmod._FindFields('FOO = 1\nFOO = 2')
    self.assertTrue(vals.has_key('FOO'))
    self.assertEquals(vals['FOO'], 1.)
    vals = srcmod._FindFields('FOO = 1\nFOO = 2', opt_ignore_duplicate=False)
    print vals
    self.assertTrue(vals.has_key('FOO'))
    self.assertEquals(vals['FOO'], 2.)

  def testGetSegmentData(self):
    field_names = '% LAT LON C==X Z'
    data = ' 1 2 3 4 \n 5 6 7 4'
    vals = srcmod._GetSegmentData('\n'.join([field_names, data]))
    self.assertTrue(len(vals), 2)
    print vals
    self.assertEquals(1, vals[0][0]['LAT'])
    self.assertEquals(2, vals[0][0]['LON'])
    self.assertEquals(3, vals[0][0]['C'])
    self.assertEquals(4, vals[0][0]['Z'])
    self.assertEquals(5, vals[0][1]['LAT'])
    self.assertEquals(6, vals[0][1]['LON'])
    self.assertEquals(7, vals[0][1]['C'])
    self.assertEquals(4, vals[0][1]['Z'])


if __name__ == '__main__':
  googletest.main()
