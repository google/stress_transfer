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
    data = [
        ":zipped_libs",
    ],
    deps = [
        "//third_party/py/earthquakes:isc",
        "//third_party/py/flask",
        "//third_party/py/utm",
    ],
)

# Shockingly, this is how you link in the cloud storage APIs -- with this obtuse
# rule and the cooresponding file in your app.
Fileset(
    name = "zipped_libs_fileset",
    out = "zipped_libs",
    entries = [
        FilesetEntry(
            files = ["zipped_libs/__init__.py"],
            strip_prefix = "zipped_libs",
        ),
        FilesetEntry(
            srcdir = "//apphosting/ext/cloudstorage/opensource",
            files = ["cloudstorage.zip"],
        ),
    ],
)
