"""Import test for ProcessSrcmod."""

import google3

import earthquakes
import earthquakes.ProcessSrcmod as process

from google3.testing.pybase import googletest


class ProcesssrcmodTest(googletest.TestCase):

  def testImport(self):
    pass

  def testRotateNinetyDegrees(self):
    x = 1  # horizontal line
    y = 0
    angle = 90
    x_rot, y_rot = process.RotateCoords(x, y, 0, 0, angle)
    self.assertAlmostEqual(x_rot, 0)  # vertical line
    self.assertAlmostEqual(y_rot, 1)

  def testFRange(self):
    self.assertEquals(len(list(process.FRange('50'))), 1)
    self.assertEquals(len(list(process.FRange('10:20:0.5'))), 20)
    self.assertEquals(len(list(process.FRange('10:20.1:0.5'))), 21)
    self.assertEquals(len(list(process.FRange('10:11:5'))), 1)
    self.assertEquals(len(list(process.FRange('10:10:0.5'))), 0)
    self.assertEquals(len(list(process.FRange('10:2:0.5'))), 0)

if __name__ == '__main__':
  googletest.main()
