# Copyright 2015 Google Inc. All rights reserved.
#
# Description:
#   Python implementation of a stress transfer from Brendan Meade at Harvard.
# For information, go/earthquakes.

package(default_visibility = ["//visibility:public"])

licenses(["notice"])  # MIT

exports_files(["LICENSE"])

py_binary(
    name = "earthquakes",
    srcs = [
        "earthquakes.py",
    ],
    deps = [
        ":ProcessSrcmod",
        ":gcs",
        "//third_party/py/requests",
    ],
)

py_test(
    name = "earthquakes_test",
    srcs = ["earthquakes_test.py"],
    deps = [
        ":earthquakes",
        "//testing/pybase",
    ],
)

py_library(
    name = "ProcessSrcmod",
    srcs = [
        "ProcessSrcmod.py",
    ],
    deps = [
        ":calc",
        ":isc",
        ":plot",
        "//third_party/py/okada_wrapper",
        "//third_party/py/pyproj",
        "//third_party/py/shapely",
        "//third_party/py/utm",
    ],
)

py_test(
    name = "ProcessSrcmod_test",
    srcs = ["ProcessSrcmod_test.py"],
    deps = [
        ":ProcessSrcmod",
        "//testing/pybase",
    ],
)

# Google Cloud Storage functions.
py_library(
    name = "gcs",
    srcs = [
        "gcs.py",
    ],
    deps = [
        "//third_party/py/apiclient",
    ],
)

# Plotting functions.
py_library(
    name = "plot",
    srcs = [
        "plot.py",
    ],
    deps = [
        "//third_party/py/matplotlib",
        "//third_party/py/numpy",
    ],
)

# All tensor calculations and such for the CSF.
py_library(
    name = "calc",
    srcs = ["calc.py"],
    deps = [
        "//pyglib",
        "//third_party/py/numpy",
    ],
)

py_test(
    name = "calc_test",
    srcs = ["calc_test.py"],
    deps = [
        ":calc",
        "//pyglib",
        "//testing/pybase",
        "//third_party/py/numpy",
    ],
)

# Srcmod reader
py_library(
    name = "srcmod",
    srcs = [
        "srcmod.py",
    ],
    deps = [
        "//third_party/py/earthquakes:gcs",
        "//third_party/py/numpy",
        "//third_party/py/scipy",
        "//third_party/py/utm",
    ],
)

py_test(
    name = "srcmod_test",
    srcs = [
        "srcmod_test.py",
    ],
    deps = [
        ":srcmod",
        "//testing/pybase",
    ],
)

py_library(
    name = "isc",
    srcs = [
        "isc.py",
    ],
    deps = [
        "//third_party/py/earthquakes:gcs",
        "//third_party/py/geopy",
    ],
)

py_test(
    name = "isc_test",
    srcs = [
        "isc_test.py",
    ],
    deps = [
        ":isc",
        "//testing/pybase",
    ],
)

py_binary(
    name = "add_work",
    srcs = [
        "add_work.py",
    ],
    deps = [
        "//pyglib",
        "//third_party/py/requests",
    ],
)
