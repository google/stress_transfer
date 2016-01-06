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
"""Plotting functions for earthquakes."""


import cStringIO
# Annoyingly, matplotlib uses Tcl and opens windows on us. Despite the fact that
# we draw to cStringIO buffer for our image, it still does it. The import and
# the use statement here prevent this.
import matplotlib
matplotlib.use('Agg')
from matplotlib import cm
import matplotlib.pyplot as plt
import numpy as np


def PlotSrcmodStressAndEarthquakesBuffer(event_srcmod, x_vec, y_vec, cfs,
                                         catalog, field, obs_depth, x_buffer,
                                         y_buffer):
  """Plots stress change, SRCMOD, geometry and aftershock locations.

  Preliminary visualziation of Coulomb failure stress field, SRCMOD
  geometry, and ISC aftershock locations.

  Args:
    event_srcmod: Dictionary with SRCMOD geometry and slip distribution
    x_vec: x-coordinates where stresses have been calculated
    y_vec: y-coordinates where stresses have been calculated
    cfs: Dictionary with Coulomb failure stress parameters
    catalog: Dictionary with aftershock locations
    field: The field to plot.
    obs_depth: The observational of the field.
    x_buffer: x-coordiantes of buffer shape
    y_buffer: y-coordinates of buffer shape

  Returns:
    Nothing but saves a figure ProcessSrcmod.png to /tmp
  """

  # Plotting specific offsets and rescalings
  pascals_to_megapascals = 1e-6
  n_contours = 10
  zero_contour = 0
  line_width = 0.5
  fault_color = 'y'
  color_black = [0.0, 0.0, 0.0]
  marker_size = 2.0
  opacity = 1.0
  min_mag = 3.0
  max_mag = 5.0
  min_day = 0
  max_day = 30
  min_d = 1e3
  max_d = 1e5
  min_cfs = -50
  max_cfs = 50
  fig_dpi = 200
  fig_width = 10
  fig_height = 8
  y_level_horizontal_line = 0.0
  vertical_subplot_spacing = 0.5

  cfs['cfsUpperLimit'] = 1e5  # For visualziation purposes.
  cfs['cfsLowerLimit'] = -1e5  # For visualization purposes.

  cfs['cfsRaw'] = cfs['cfs'].copy()
  high_1 = (cfs['cfs'] > cfs['cfsUpperLimit']).nonzero()
  high_2 = (cfs['cfs'] > 0).nonzero()
  high_indices = np.intersect1d(np.array(high_1), np.array(high_2))
  low_1 = (cfs['cfs'] < cfs['cfsLowerLimit']).nonzero()
  low_2 = (cfs['cfs'] < 0).nonzero()
  low_indices = np.intersect1d(np.array(low_1), np.array(low_2))
  cfs['cfs'][high_indices] = cfs['cfsUpperLimit']
  cfs['cfs'][low_indices] = cfs['cfsLowerLimit']

  # Generate figure showing fault geometry and CFS field.
  fig = plt.figure(facecolor='white', figsize=(fig_width, fig_height),
                   dpi=fig_dpi)
  plt.subplot(1, 2, 1)
  ax = fig.gca()
  # Both of these contouring calls are plotting (erronously) in some concave
  # regions for some reason???
  plt.tricontourf(x_vec.flatten(), y_vec.flatten(),
                  pascals_to_megapascals * cfs['cfs'].flatten(),
                  n_contours, cmap=cm.bwr,
                  origin='lower', hold='on', extend='both')
  plt.tricontour(x_vec.flatten(), y_vec.flatten(),
                 pascals_to_megapascals * cfs['cfs'].flatten(), zero_contour,
                 linewidths=line_width,
                 colors='w', origin='lower', hold='on')

  # Draw the buffer perimeter
  ax.plot(x_buffer, y_buffer, color=color_black, linewidth=line_width)

  # Plot ISC earthquake locations if they are close enough to the epicenter.
  for i in range(len(catalog['xUtm'])):
    ax.plot(catalog['xUtm'][i], catalog['yUtm'][i], marker='o',
            color=color_black, markeredgecolor='none',
            markerfacecoloralt='gray',
            markersize=marker_size, alpha=opacity)

  # Plot the edges of each fault patch.
  for i in range(len(event_srcmod['x1'])):
    ax.plot([event_srcmod['x1Utm'][i], event_srcmod['x2Utm'][i]],
            [event_srcmod['y1Utm'][i], event_srcmod['y2Utm'][i]],
            color=fault_color, linewidth=line_width)
    ax.plot([event_srcmod['x2Utm'][i], event_srcmod['x4Utm'][i]],
            [event_srcmod['y2Utm'][i], event_srcmod['y4Utm'][i]],
            color=fault_color, linewidth=line_width)
    ax.plot([event_srcmod['x1Utm'][i], event_srcmod['x3Utm'][i]],
            [event_srcmod['y1Utm'][i], event_srcmod['y3Utm'][i]],
            color=fault_color, linewidth=line_width)
    ax.plot([event_srcmod['x3Utm'][i], event_srcmod['x4Utm'][i]],
            [event_srcmod['y3Utm'][i], event_srcmod['y4Utm'][i]],
            color=fault_color, linewidth=line_width)

  # Standard decorations.
  plt.title(event_srcmod['tag'])
  plt.axis('equal')
  plt.axis('off')

  # FC as a function of distance from SRCMOD epicenter
  plt.subplot(3, 2, 2)
  ax = fig.gca()
  ax.plot([np.log10(min_d), np.log10(max_d)],
          [y_level_horizontal_line, y_level_horizontal_line],
          marker=' ', color='k', linestyle='-',
          alpha=opacity)
  positives = 0
  negatives = 0
  for i in range(len(catalog['xUtm'])):
    if field[i] > 0:
      positives += 1
      color = 'red'
    else:
      negatives += 1
      color = 'blue'
    ax.plot(np.log10(catalog['distanceToEpicenter'][i]),
            pascals_to_megapascals * field[i], marker='o', color=color,
            markeredgecolor='none', markerfacecoloralt='gray',
            markersize=marker_size,
            alpha=opacity)
  ax.set_xlim([np.log10(min_d), np.log10(max_d)])
  ax.set_ylim([min_cfs, max_cfs])
  plt.xlabel(r'$\log_{10}\,d \, \mathrm{(m)}$')
  plt.ylabel(r'$\Delta \mathrm{FC}$')
  plt.title(r'$N(\Delta\mathrm{FC}>0) = $' + str(positives) +
            r', $N(\Delta\mathrm{FC}<0) = $' + str(negatives))

  # FC as a function of time
  plt.subplot(3, 2, 4)
  ax = fig.gca()
  ax.plot([min_day, max_day],
          [y_level_horizontal_line, y_level_horizontal_line],
          marker=' ', color='k', linestyle='-',
          alpha=opacity)
  for i in range(len(catalog['xUtm'])):
    color = 'red' if (field[i] > 0) else 'blue'
    ax.plot((catalog['datetime'][i] - event_srcmod['datetime']).days,
            pascals_to_megapascals * field[i], marker='o', color=color,
            markeredgecolor='none', markerfacecoloralt='gray',
            markersize=marker_size, alpha=opacity)
  ax.set_ylim([-0.5e2, 0.5e2])
  ax.set_ylim([min_cfs, max_cfs])
  plt.xlabel(r'$t \, \mathrm{(days)}$')
  plt.ylabel(r'$\Delta \mathrm{FC}$')

  # FC as a function of aftershock magnitude
  plt.subplot(3, 2, 6)
  ax = fig.gca()
  ax.plot([min_mag, max_mag],
          [y_level_horizontal_line, y_level_horizontal_line],
          marker=' ', color='k', linestyle='-',
          alpha=opacity)
  for i in range(len(catalog['xUtm'])):
    if field[i] > 0:
      ax.plot(catalog['magnitude'][i],
              pascals_to_megapascals * field[i], marker='o',
              color='red', markeredgecolor='none', markerfacecoloralt='gray',
              markersize=marker_size, alpha=opacity)
    else:
      ax.plot(catalog['magnitude'][i],
              pascals_to_megapascals * field[i], marker='o',
              color='blue', markeredgecolor='none', markerfacecoloralt='gray',
              markersize=marker_size, alpha=opacity)
  ax.set_xlim([min_mag, max_mag])
  ax.set_ylim([min_cfs, max_cfs])
  plt.xlabel(r'$\mathrm{M_W}$')
  plt.ylabel(r'$\Delta \mathrm{FC}$')

  # Adjust subplot spacing, render, and save
  plt.subplots_adjust(left=None, bottom=None, right=None, top=None, wspace=None,
                      hspace=vertical_subplot_spacing)
  plt.show()
  stream = cStringIO.StringIO()
  plt.savefig(stream, format='png')
  return stream.getvalue()
