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
"""Does the majority of the earthquake work. go/eartquakes for discussion."""

from __future__ import division

import datetime
import logging
import math

import calc
import isc
import numpy as np
from okada_wrapper import dc3dwrapper
import plot
from shapely.geometry import Point
from shapely.ops import cascaded_union
import srcmod


def GetIscEventcatalog(start_date_time, days, pos, catalog_type):
  """Reads the ISC event catalog, and munges data for rest of file.

  Args:
    start_date_time: datetime of the for the quake.
    days: number of days from start_date_time we'd like in our ISC data.
    pos: lat, long tuple of the quake location.
    catalog_type: one of 'comp', 'rev', 'esb' for catalog type.
  Returns:
    ISC data as a dictionary of lists.
  """
  # Read the isc data. Note that we take any data points within 1000 km, which
  # is a huge distance. We let the polygon distance calculation below pull it
  # in closer.
  data = isc.ReadISCData('gs://clouddfe-cfs/isc', catalog_type, start_date_time,
                         days, pos, 1000)

  # Munge the data. Brendan's calculations have different field names from
  # what's returned from the ISC reader. Likely we want to remove this step.
  # TODO(jfaller, meadeb): Make field names consistent.
  ret = {}
  ret['yr'] = [x['date_time'].year for x in data]
  ret['mon'] = [x['date_time'].month for x in data]
  ret['day'] = [x['date_time'].day for x in data]
  ret['hr'] = [x['date_time'].hour for x in data]
  ret['min'] = [x['date_time'].minute for x in data]
  ret['sec'] = [x['date_time'].second for x in data]
  ret['latitude'] = [x['lat'] for x in data]
  ret['longitude'] = [x['lon'] for x in data]
  ret['depth'] = [x['depth'] for x in data]
  ret['magnitude'] = [x['magnitude'] for x in data]
  ret['datetime'] = [x['date_time'] for x in data]

  return ret


def CalcOkada(x, y, z, event_srcmod, lambda_lame, mu_lame):
  """Calculate strains and stresses from SRCMOD event with Okada (1992).

  Calculate nine element symmetric elastic strain and stress tensors at
  observation coordinates using Okada (1992).  Dislocation parameters are
  given an event_srcmod dictionary which contains the geometry and slip
  distribution for a given SRCMOD event.

  Args:
    x: List of x-coordinates of observation points (meters)
    y: List of y-coordinates of observation points (meters)
    z: List of z-coordinates of observation points (meters, negative down)
    event_srcmod: Dictionary with SRCMOD event parameters for one event
    lambda_lame: Lame's first parameter (Pascals)
    mu_lame: Lame's second parameter, shear modulus (Pascals)

  Returns:
    strains, stresses: Lists of 3x3 numpy arrays with full strain
       and stress tensors at each 3d set of obervation coordinates
  """
  strains = []
  stresses = []
  alpha = (lambda_lame + mu_lame) / (lambda_lame + 2 * mu_lame)

  for j in range(len(x)):
    strain = np.zeros((3, 3))
    stress = np.zeros((3, 3))
    for i in range(len(event_srcmod['x1'])):
      x_rot, y_rot = RotateCoords(x[j], y[j],
                                  event_srcmod['x1Utm'][i],
                                  event_srcmod['y1Utm'][i],
                                  -1.0 * event_srcmod['angle'][i])

      _, _, gradient_tensor = dc3dwrapper(alpha,
                                          [x_rot, y_rot, z[j]],
                                          event_srcmod['z3'][i],
                                          event_srcmod['dip'][i],
                                          [0.0, event_srcmod['length'][i]],
                                          [0.0, event_srcmod['width'][i]],
                                          [event_srcmod['slipStrike'][i],
                                           event_srcmod['slipDip'][i],
                                           0.0])

      # Tensor algebra definition of strain
      cur_strain = 0.5 * (gradient_tensor.T + gradient_tensor)
      strain += cur_strain
      # Tensor algebra constituitive relationship for elasticity
      stress += (lambda_lame * np.eye(cur_strain.shape[0]) *
                 np.trace(cur_strain) + 2 * mu_lame * cur_strain)
    strains.append(strain)
    stresses.append(stress)
  return strains, stresses


def RotateCoords(x, y, x_offset, y_offset, angle):
  """Rotate x and y observation coordinates in a local reference frame.

  Rotate a single set of x and y observation coordinates into a local
  reference frame appropriate for okada_wrapper call.  The two steps are: 1)
  calculate x and y coordinates relative to fault coordinates system with a
  translation and 2) rotate to correct for strike (already converted to a
  Cartesian angle).

  Args:
    x: x-coordinate to rotate
    y: y-coordinate to rotate
    x_offset: x-coordinate of local fault cetered coordinate system
    y_offset: y-coordinate of local fault cetered coordinate system
    angle: Angle (Cartesian, not strike) to rotate coordinates by (degrees).

  Returns:
    x and y coordinates rotated into a local reference frame.
  """
  x_local = x - x_offset
  y_local = y - y_offset
  angle = np.radians(1.0 * angle)
  rot_matrix = np.array([[np.cos(angle), -np.sin(angle)],
                         [np.sin(angle), np.cos(angle)]])
  x_rot_vec = np.dot(rot_matrix, np.array([x_local, y_local]))
  return x_rot_vec[0], x_rot_vec[1]


def CfsVectorsFromAzimuth(fault_azimuth, fault_dip):
  """Finds the CFS normal vectors.

  Args:
    fault_azimuth: Degress of the fault azimuth.
    fault_dip: Degress of the fault.
  Returns:
    Tuple of rotated vectors.
  """
  # This is the angle trhough which we rotate n_vec_normal_ref.
  rotation_angle = math.radians(fault_dip - 90)
  fault_azimuth = math.radians(fault_azimuth)
  r_temp_azimuth = np.array([[math.cos(fault_azimuth),
                              math.sin(fault_azimuth), 0],
                             [-math.sin(fault_azimuth),
                              math.cos(fault_azimuth), 0],
                             [0, 0, 1]])
  r_temp_dip = np.array([[math.cos(rotation_angle),
                          math.sin(rotation_angle), 0],
                         [-math.sin(rotation_angle),
                          math.cos(rotation_angle), 0],
                         [0, 0, 1]])
  n_vec_in_plane = np.dot(r_temp_azimuth, [0, 1, 0])
  n_vec_in_plane = np.dot(r_temp_dip, n_vec_in_plane)
  n_vec_normal = np.dot(r_temp_azimuth, [1, 0, 0])
  n_vec_normal = np.dot(r_temp_dip, n_vec_normal)
  return (n_vec_in_plane, n_vec_normal)


def CalcFaultBuffer(event_srcmod, distance):
  """Finds the polygon around the srcmod data for interesting ISC points.

  Args:
    event_srcmod: The srcmod data.
    distance: The "balloon" distance for our polygon around the faults.
  Returns:
    A triplet of the x/y/polygon.
  """
  # Create buffer around fault with shapely.
  circles = []
  # Plot the edges of each fault patch.
  for i in range(len(event_srcmod['x1'])):
    circles.append(Point(event_srcmod['x1Utm'][i],
                         event_srcmod['y1Utm'][i]).buffer(distance))
    circles.append(Point(event_srcmod['x2Utm'][i],
                         event_srcmod['y2Utm'][i]).buffer(distance))
    circles.append(Point(event_srcmod['x3Utm'][i],
                         event_srcmod['y3Utm'][i]).buffer(distance))
    circles.append(Point(event_srcmod['x4Utm'][i],
                         event_srcmod['y4Utm'][i]).buffer(distance))
  polygon_buffer = cascaded_union(circles)
  temp = np.array(polygon_buffer.exterior).flatten()
  x_buffer = temp[0::2]
  y_buffer = temp[1::2]
  return (x_buffer, y_buffer, polygon_buffer)


def CalcBufferGridPoints(x_buffer, y_buffer, polygon_buffer, spacing_grid):
  """Finds the grid points for our buffer around the fault."""
  x_fill_vec = np.arange(np.min(x_buffer), np.max(x_buffer), spacing_grid)
  y_fill_vec = np.arange(np.min(y_buffer), np.max(y_buffer), spacing_grid)
  x_buffer_fill_grid, y_buffer_fill_grid = np.meshgrid(x_fill_vec, y_fill_vec)

  # Select only those grid points inside of buffered region.
  x_buffer_fill_grid = x_buffer_fill_grid.flatten()
  y_buffer_fill_grid = y_buffer_fill_grid.flatten()
  indices_to_delete = []
  for i in range(len(x_buffer_fill_grid)):
    candidate = Point(x_buffer_fill_grid[i], y_buffer_fill_grid[i])
    if not polygon_buffer.contains(candidate):
      indices_to_delete.append(i)
  x_buffer_fill_grid = np.delete(x_buffer_fill_grid, indices_to_delete)
  y_buffer_fill_grid = np.delete(y_buffer_fill_grid, indices_to_delete)
  return (x_buffer_fill_grid, y_buffer_fill_grid)


def GetNearFieldIscEventsBuffer(catalog, event_srcmod, polygon_buffer):
  """Removes points from the ISC buffer that aren't in the polygon.

  Args:
    catalog: Dictionary of the ISC data points. (modified in place.)
    event_srcmod: Srcmod data.
    polygon_buffer: Describes the polygon for which we're keeping ISC data.
  Returns:
    The modified catalog (also modified in place).
  """
  # Convert longitude and latitudes to local UTM coordinates.
  catalog['xUtm'], catalog['yUtm'] = event_srcmod['projEpicenter'](
      catalog['longitude'], catalog['latitude'])

  # Determine whether or not the catalog events are withing the polygon buffer.
  indices_to_delete = []
  catalog['distanceToEpicenter'] = []
  for i in range(len(catalog['xUtm'])):
    distance = np.sqrt(
        (catalog['xUtm'][i] - event_srcmod['epicenterXUtm']) ** 2 +
        (catalog['yUtm'][i] - event_srcmod['epicenterYUtm']) ** 2)
    catalog['distanceToEpicenter'].append(distance)
    pt = Point(catalog['xUtm'][i], catalog['yUtm'][i])
    if not polygon_buffer.contains(pt):
      indices_to_delete.append(i)

  # Remove all catalog earthquakes that are not in field of interest from lists
  # in dict catalog.
  indices_to_delete = sorted(indices_to_delete, reverse=True)
  for key in catalog:
    for i in indices_to_delete:
      del catalog[key][i]
  return catalog


def ModelQuake(filename, coefficient_of_friction, mu_lambda_lame,
               near_field_distance, spacing_grid, obs_depth, days,
               catalog_type):
  """Models a quake.

  TODO(jfaller): Read the data from bigtable.

  Args:
    filename: Srcmod filename.
    coefficient_of_friction: The coefficent of friction.
    mu_lambda_lame: Used to determine Poisson's ratio.
    near_field_distance: Distance from fault for shapely buffer.
    spacing_grid: For plotting.
    obs_depth: For plotting.
    days: Number of days for which to plot.
    catalog_type: ISC catalog type.
  Returns:
    Dictionary of the failure criteria of our calcuation. (should be 36 key
    value pairs)
  """
  event_srcmod = srcmod.ReadSrcmodFile(filename)

  # CFS results get pumped into this datastructure.
  cfs = dict()

  # Generate regular grid over region inside of fault buffer
  x_buffer, y_buffer, polygon_buffer = CalcFaultBuffer(event_srcmod,
                                                       near_field_distance)
  x_buffer_fill_grid, y_buffer_fill_grid = CalcBufferGridPoints(
      x_buffer, y_buffer, polygon_buffer, spacing_grid)

  # Append boundary coordinates to filled buffer for nice plotting
  x_buffer_fill_grid = np.append(x_buffer_fill_grid, x_buffer)
  y_buffer_fill_grid = np.append(y_buffer_fill_grid, y_buffer)

  # Calculate stress tensor at observation coordinates
  strains, stresses = CalcOkada(x_buffer_fill_grid, y_buffer_fill_grid,
                                obs_depth + 0 * x_buffer_fill_grid,
                                event_srcmod, mu_lambda_lame, mu_lambda_lame)
  strains_dev = calc.DeviatoricTensor(strains)
  stresses_dev = calc.DeviatoricTensor(stresses)

  # Resolve Coulomb failure stresses on reciever plane
  cfs['faultAzimuth'] = event_srcmod['strikeMean']
  cfs['faultDip'] = event_srcmod['dipMean']
  (cfs['nVecInPlane'], cfs['nVecNormal']) = CfsVectorsFromAzimuth(
      cfs['faultAzimuth'], cfs['faultDip'])
  cfs['cfs'] = calc.Cfs(stresses, cfs['nVecNormal'], cfs['nVecInPlane'],
                        coefficient_of_friction)

  # Create the data we need to store off in the datastore. We start with the
  # stresses and strains, their deviatorics, and add back in the 36 other
  # parameters described below:
  #
  #   9 scalars we'll calculate for each of 4 tensor fields. (9 * 4 = 36)
  #     Tensor fields:
  #        1) Strain
  #        2) Deviatoric Strain
  #        3) Stress
  #        4) Deviatoric Stress
  #     Scalars:
  #        1) Classical Coulomb Failure Criterion: calcCfs
  #        2) Total Shear Coulomb Failure Criterion: calcCfsTotal
  #        3) Normal-only component of Coulomb Failure Criterion: calcCfsNormal
  #        4) Classical Shear-only Coulomb Failure Criterion: calcCfs
  #        5) Total Shear-only Coulomb Failure Criterion: calcMaximumTotal
  #        6) Maximum shear: calcMaximumShear
  #        7) First invariant of strain/stress tensor: calcTensorInvariants
  #        8) Second invariant of strain/stress tensor: calcTensorInvariants
  #        9) Third invariant of strain/stress tensor: calcTensorInvariants
  criteria = {
      'strains': strains,
      'stresses': stresses,
      'strains_dev': strains_dev,
      'stresses_dev': stresses_dev,
      'y_buffer_fill_grid': y_buffer_fill_grid,
      'x_buffer_fill_grid': x_buffer_fill_grid,
      'srcmod': event_srcmod,
  }
  criteria.update(locals())  # Save off parameters.
  for x, name in zip([strains, stresses, strains_dev, stresses_dev],
                     ['strains', 'stresses', 'strains_deviatoric',
                      'stresses_deviatoric']):
    criteria[name + '_cfs'] = calc.Cfs(x, cfs['nVecNormal'], cfs['nVecInPlane'],
                                       coefficient_of_friction)
    criteria[name + '_cfs_shear_only'] = calc.Cfs(x, cfs['nVecNormal'],
                                                  cfs['nVecInPlane'], 0)
    tensor_invariants = calc.TensorInvariants(x)
    for i in range(len(tensor_invariants)):
      criteria[name + '_i{}'.format(i)] = tensor_invariants[i]
    criteria[name + '_max_shear'] = calc.MaximumShear(x)
    criteria[name + '_cfs_total'] = calc.CfsTotal(x, cfs['nVecNormal'],
                                                  cfs['nVecInPlane'],
                                                  coefficient_of_friction)
    criteria[name + '_cfs_total_shear_only'] = calc.CfsTotal(x,
                                                             cfs['nVecNormal'],
                                                             cfs['nVecInPlane'],
                                                             0)
    criteria[name + '_cfs_normal'] = calc.CfsNormal(x, cfs['nVecNormal'],
                                                    coefficient_of_friction)

  # Visualize the quake
  start_date_time = event_srcmod['datetime'] + datetime.timedelta(days=1)
  pos = (event_srcmod['epicenterLatitude'], event_srcmod['epicenterLongitude'])

  catalog = GetIscEventcatalog(start_date_time, days, pos, catalog_type)
  catalog = GetNearFieldIscEventsBuffer(catalog, event_srcmod, polygon_buffer)
  criteria['isc'] = catalog

  # Calculate Coulomb failure stress at ISC event locations
  field = []
  for i in range(len(catalog['xUtm'])):
    logging.debug('Calculating Okada %d of %d', i, len(catalog['xUtm']))
    _, stresses_isc = CalcOkada(np.array([catalog['xUtm'][i]]),
                                np.array([catalog['yUtm'][i]]),
                                np.array([catalog['depth'][i]]),
                                event_srcmod, mu_lambda_lame, mu_lambda_lame)
    field.append(calc.Cfs(stresses_isc, cfs['nVecNormal'], cfs['nVecInPlane'],
                          coefficient_of_friction)[0])

  # Plot CFS with SRCMOD event and ISC events
  try:
    graph = plot.PlotSrcmodStressAndEarthquakesBuffer(event_srcmod,
                                                      x_buffer_fill_grid,
                                                      y_buffer_fill_grid, cfs,
                                                      catalog,
                                                      field, obs_depth,
                                                      x_buffer, y_buffer)
  except:
    graph = None
  # Remove the projector, which doesn't pickle really well.
  del criteria['srcmod']['projEpicenter']
  # Flatten criteria.
  ret = {}
  for k, v in criteria.items():
    try:
      ret[k] = v.tolist()
    except AttributeError:
      ret[k] = v
  return ret, graph

