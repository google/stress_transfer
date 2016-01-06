# Appengine BUILD file.
#
# Description:
#   App engine BUILD file.
package(default_visibility = ["//visibility:public"])

licenses(["permissive"])  # Googler created addition to package.

exports_files(["LICENSE"])

py_appengine_binary(
    name = "earthquakes",
    srcs = [
        "appengine_config.py",
        "main.py",
        "process.py",
    ],
    configs = [
        "app.yaml",
        "index.yaml",
    ],
    deps = [
        "//third_party/py/earthquakes:isc",
        "//third_party/py/flask",
        "//third_party/py/utm",
    ],
)
