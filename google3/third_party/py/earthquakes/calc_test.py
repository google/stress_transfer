"""Tests for earthquakes calcuation module."""

import collections

import google3

import earthquakes.calc as calc
import numpy as np

from google3.testing.pybase import googletest


class DeviatoricTest(googletest.TestCase):

  def _BlankInput(self):
    """Generate a tensor that only contains main diagonal data."""
    ret = {}
    ret['sxx'] = [0, 3]
    ret['syy'] = [1, 4]
    ret['szz'] = [2, 5]
    return ret

  def _Convert(self, vec):
    ret = []
    for i in range(len(vec['sxx'])):
      ret.append(np.diag([vec['sxx'][i], vec['syy'][i], vec['szz'][i]]))
    return ret

  def testDevaitor(self):
    tensor = self._BlankInput()
    tensor = self._Convert(tensor)
    val = calc.DeviatoricTensor(tensor)
    for i in range(len(val)):
      avg = sum(range(i * 3, i * 3 + 3)) / 3.0
      self.assertEquals(val[i][0][0], tensor[i][0][0] - avg)
      self.assertEquals(val[i][1][1], tensor[i][1][1] - avg)
      self.assertEquals(val[i][2][2], tensor[i][2][2] - avg)


class InvariantTest(googletest.TestCase):

  def _BlankInput(self):
    """Generate a tensor full of ones."""
    return collections.defaultdict(lambda: list([1]))

  def _Convert(self, vec):
    ret = []
    for i in range(len(vec['sxx'])):
      ret.append(np.array([[vec['sxx'][i], vec['sxy'][i], vec['sxz'][i]],
                           [vec['sxy'][i], vec['syy'][i], vec['syz'][i]],
                           [vec['sxz'][i], vec['syz'][i], vec['szz'][i]]]))
    return ret

  def testInvariant(self):
    tensor = self._BlankInput()
    tensor = self._Convert(tensor)
    i1, i2, i3 = calc.TensorInvariants(tensor)
    self.assertEquals(i1, [3])
    self.assertEquals(i2, [0])
    self.assertEquals(i3, [0])


if __name__ == '__main__':
  googletest.main()
