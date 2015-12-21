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
"""Tensor calcuations for the failure criteria for the earthquakes project.

This file pulls all the nitty-gritty math out of the ProcessSrcmod.py. This is
just to make unit testing easier, and generally, make ProcessSrcmod more
readable.
"""

import numpy as np


def Cfs(tensors, n_vec_normal, n_vec_in_plane, coefficient_of_friction):
  """Calculate classical Coulomb criteria.

  Calculate the normal Coulomb criteria on a specified reciever plane.
  This calculation ignores the effects of a shear component.
  TODO(meadeb): Clarify sign convention

  Args:
    tensors: A list of symmetric 3x3 arrays.
    n_vec_normal: a 3-element unit vector normal to the receiver fault plane
    n_vec_in_plane: a 3-element unit vector in the direction of preferred slip
    coefficient_of_friction: scalar, coefficient of friction
        (0-0.85, typically)

  Returns:
    cfc: a list of Coulomb failure criteria values.
  """
  cfc = []
  for tensor in tensors:
    delta_tau = np.dot(np.dot(tensor, n_vec_normal), n_vec_in_plane)
    delta_sigma = np.dot(np.dot(tensor, n_vec_normal), n_vec_normal)
    cfc.append(delta_tau + coefficient_of_friction * delta_sigma)
  return np.array(cfc)


def CfsNormal(tensors, n_vec_normal, coefficient_of_friction):
  """Calculate normal only Coulomb criteria.

  Calculate the normal Coulomb criteria on a specified reciever plane.
  This calculation ignores the effects of normal component and
  coefficient of friction.
  TODO(meadeb): Clarify sign convention

  Args:
    tensors: A list of symmetric 3x3 arrays.
    n_vec_normal: a 3-element unit vector normal to the receiver fault plane
    coefficient_of_friction: scalar, coefficient of friction
        (0-0.85, typically)

  Returns:
    cfc: a list of normal only Coulomb failure criteria values.
  """
  cfc = []
  for tensor in tensors:
    delta_sigma = np.dot(np.dot(tensor, n_vec_normal), n_vec_normal)
    cfc.append(coefficient_of_friction * delta_sigma)
  return np.array(cfc)


def CfsTotal(tensors, n_vec_normal, n_vec_in_plane, coefficient_of_friction):
  """Calculate total Coulomb criteria.

  Calculate the normal Coulomb criteria on a specified reciever plane.
  This calculation ignores the effects of normal component and
  coefficient of friction.
  TODO(meadeb): Clarify sign convention

  Args:
    tensors: A list of symmetric 3x3 arrays.
    n_vec_normal: a 3-element unit vector normal to the receiver fault plane
    n_vec_in_plane: a 3-element unit vector in the direction of preferred slip
    coefficient_of_friction: scalar, coefficient of friction
        (0-0.85, typically)

  Returns:
    cfc: a list of total Coulomb failure criteria values.
  """
  cfc = []
  n_vec_cross = np.cross(n_vec_normal, n_vec_in_plane)
  for tensor in tensors:
    delta_tau1 = np.dot(np.dot(tensor, n_vec_normal), n_vec_in_plane)
    delta_tau2 = np.dot(np.dot(tensor, n_vec_normal), n_vec_cross)
    delta_sigma = np.dot(np.dot(tensor, n_vec_normal), n_vec_normal)
    cfc.append(np.abs(delta_tau1) + np.abs(delta_tau2)
               + coefficient_of_friction * delta_sigma)
  return np.array(cfc)


def MaximumShear(tensors):
  """Calculate maximum shear symmetric 3x3 tensor.

  Calculate the maximum shear of a symmetric 3x3 tensor. This is just half the
  difference between the largest and smallest eigenvalues.

  Args:
    tensors: A list of symmetric 3x3 arrays.

  Returns:
    ret: a list of maximum shear values.
  """
  ret = []
  for tensor in tensors:
    eigen_values = list(np.linalg.eigvalsh(tensor))
    ret.append((max(eigen_values) - min(eigen_values)) / 2.0)
  return np.array(ret)


def TensorInvariants(tensors):
  """Calculate invariants of a symmetric 3x3 tensor.

  Calculate the invariants component of a symmetric 3x3 tensor. Forumulas are
  according following Malvern (1969) and conveniently replicated on Wikipedia:
  https://en.wikipedia.org/wiki/Cauchy_stress_tensor

  Args:
    tensors: A list of symmetric 3x3 arrays.

  Returns:
    Three lists (i1, i2, i3) of numpy arrays.
  """
  i1 = []
  i2 = []
  i3 = []
  for tensor in tensors:
    i1.append(np.trace(tensor))
    i2.append(np.linalg.det(tensor[0:2, 0:2]) +
              np.linalg.det(tensor[1:3, 0:2]) +
              np.linalg.det(tensor[1:3, 1:3]))
    i3.append(np.linalg.det(tensor))
  return np.array(i1), np.array(i2), np.array(i3)


def DeviatoricTensor(tensors):
  """Calculate deviator of a 3x3 tensor.

  Calculate the deviatoric component of a 3x3 tensor. This done by subtracting
  out the isotropic part of the full tensor given by the average of the main
  diagonal elements. Operates on either a single 3x3 tensor or a list of 3x3
  arrays.

  Args:
    tensors: A list of 3x3 arrays.

  Returns:
    A list of 3x3 arrays with the isotropic component subtracted out.
  """
  ret = []
  for tensor in tensors:
    avg = np.trace(tensor) / 3.
    ret.append(tensor - avg * np.eye(3))
  return np.array(ret)
