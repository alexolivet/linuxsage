# Local override of python-for-android onnxruntime_np1 recipe.
#
# Fix for build failure when `protoc` is missing on the host:
#   sh.ErrorReturnCode_1: RAN: /usr/bin/which protoc
#
# Instead of requiring a system `protoc` binary, we use `grpcio-tools`, which
# bundles a protoc implementation accessible via `python -m grpc_tools.protoc`.
# We create a small wrapper script and point CMake to it.

from __future__ import annotations

import os
import shutil
import zipfile
from multiprocessing import cpu_count
from os.path import exists, join
from urllib.request import urlretrieve

import sh

from pythonforandroid.recipe import PyProjectRecipe, Recipe
from pythonforandroid.toolchain import current_directory, shprint


class OnnxRuntimeRecipe(PyProjectRecipe):
    version = "1.22.1"
    site_packages_name = "onnxruntime"
    url = "https://github.com/microsoft/onnxruntime/archive/refs/tags/v{version}.tar.gz"

    # Building with isolation can fail in some p4a hostpython environments
    # (e.g. setuptools.build_meta import issues). Use hostpython-installed
    # build tooling instead.
    extra_build_args = [
        "--no-isolation",
        "--skip-dependency-check",
    ]

    depends = ["setuptools", "wheel", "numpy1", "protobuf", "pybind11"]
    patches = [
        "patches/onnx_numpy.patch",
        "patches/mlasi_bfloat.patch",
    ]
    build_in_src = True

    def _ensure_protoc(self, build_dir: str) -> str:
        """Return path to a *real* protoc binary usable by ORT/ONNX CMake.

        Important:
        - `grpcio-tools` provides `python -m grpc_tools.protoc`, but that build
          does not always include the C++ generator, which leads to:
            protoc-gen-cpp: program not found
        - ORT/ONNX need C++ proto generation, so we download an official
          protoc release if `protoc` isn't already available on the host.
        """

        sys_protoc = shutil.which("protoc")
        if sys_protoc:
            return sys_protoc

        tools_dir = join(build_dir, "_host_tools")
        protoc_dir = join(tools_dir, "protoc")
        protoc_bin = join(protoc_dir, "bin", "protoc")

        if exists(protoc_bin):
            return protoc_bin

        os.makedirs(tools_dir, exist_ok=True)

        # IMPORTANT: protoc version must match the protobuf headers used by
        # ORT/ONNX.
        # ORT v1.22.x vendors protobuf 3.21.12 (see protobuf common.h
        # GOOGLE_PROTOBUF_VERSION 3021012).
        #
        # Protobuf's GitHub release tags and binary asset names in the 3.21.x
        # line use the *"21.12"* format:
        #   tag:      v21.12
        #   filename: protoc-21.12-linux-x86_64.zip
        protoc_release = "21.12"
        zip_name = f"protoc-{protoc_release}-linux-x86_64.zip"
        url = (
            "https://github.com/protocolbuffers/protobuf/releases/download/"
            f"v{protoc_release}/{zip_name}"
        )
        zip_path = join(tools_dir, zip_name)

        urlretrieve(url, zip_path)

        os.makedirs(protoc_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(protoc_dir)

        try:
            os.remove(zip_path)
        except OSError:
            pass

        os.chmod(protoc_bin, 0o755)
        return protoc_bin

    def get_recipe_env(self, arch=None):
        env = super().get_recipe_env(arch)
        python_include_dir = self.ctx.python_recipe.include_root(arch.arch)
        env["CPPFLAGS"] += f" -Wno-unused-variable -I{python_include_dir}"
        env["CXXFLAGS"] += f" -I{python_include_dir}"
        env["CFLAGS"] += f" -I{python_include_dir}"
        env["Python_INCLUDE_DIRS"] = python_include_dir
        return env

    def build_arch(self, arch):
        env = self.get_recipe_env(arch)
        ANDROID_PLATFORM = str(self.ctx.ndk_api)

        build_dir = self.get_build_dir(arch.arch)
        cmake_dir = join(build_dir, "cmake")
        capi_dir = join(build_dir, "onnxruntime", "capi")
        dist_dir = join(build_dir, "dist")

        python_include_dir = self.ctx.python_recipe.include_root(arch.arch)
        pybind11_recipe = self.get_recipe("pybind11", self.ctx)
        pybind11_include_dir = pybind11_recipe.get_include_dir(arch)

        python_link_root = self.ctx.python_recipe.link_root(arch.arch)
        python_link_version = self.ctx.python_recipe.link_version
        python_library = join(python_link_root, f"libpython{python_link_version}.so")

        python_site_packages = self.ctx.get_site_packages_dir(arch)
        python_include_numpy = join(python_site_packages, "numpy", "core", "include")

        toolchain_file = join(self.ctx.ndk_dir, "build/cmake/android.toolchain.cmake")

        shprint(sh.mkdir, "-p", capi_dir)
        shprint(sh.mkdir, "-p", dist_dir)

        protoc_exec = self._ensure_protoc(build_dir)

        cmake_args = [
            "cmake",
            cmake_dir,
            # ORT pulls in some deps (e.g. dlpack) whose CMakeLists have very
            # old `cmake_minimum_required()` declarations.
            # Newer CMake versions error out unless a minimum policy version is
            # specified.
            "-DCMAKE_POLICY_VERSION_MINIMUM=3.5",
            f"-DCMAKE_TOOLCHAIN_FILE={toolchain_file}",
            f"-DANDROID_ABI={arch.arch}",
            f"-DANDROID_PLATFORM={ANDROID_PLATFORM}",
            "-Donnxruntime_ENABLE_PYTHON=ON",
            "-Donnxruntime_BUILD_SHARED_LIB=OFF",
            "-DPYBIND11_USE_CROSSCOMPILING=TRUE",
            "-Donnxruntime_USE_NNAPI_BUILTIN=ON",
            "-Donnxruntime_USE_XNNPACK=ON",
            f"-DONNX_CUSTOM_PROTOC_EXECUTABLE={protoc_exec}",
            f"-DPython_NumPy_INCLUDE_DIR={python_include_numpy}",
            f"-DPython_EXECUTABLE={self.ctx.hostpython}",
            f"-Dpybind11_INCLUDE_DIRS={pybind11_include_dir};{python_include_dir};{python_include_numpy}",
            f"-DPython_LIBRARY={python_library}",
            f"-DPython_LIBRARIES={python_library}",
            "-DCMAKE_BUILD_TYPE=RELEASE",
            "-Donnxruntime_BUILD_UNIT_TESTS=OFF",
        ]

        with current_directory(build_dir):
            shprint(sh.Command("cmake"), *cmake_args, _env=env)
            shprint(sh.make, "-j" + str(cpu_count()), _env=env)

        super().build_arch(arch)


recipe = OnnxRuntimeRecipe()
