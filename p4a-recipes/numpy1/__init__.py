# Local override of python-for-android numpy1 recipe.
#
# Fix for build failures like:
#   pyproject_hooks._impl.BackendUnavailable: Cannot import 'mesonpy'
#
# NumPy uses the `mesonpy` build backend (provided by the `meson-python` PyPI
# package). In some p4a/build environments build isolation can be disabled or
# otherwise mis-detected, which leads to NumPy's build backend import failing.
#
# We make the build more robust by ensuring `meson-python` is installed into
# hostpython before building.

from os.path import join
import shutil

from pythonforandroid.recipe import Recipe, MesonRecipe
from pythonforandroid.logger import error


NUMPY_NDK_MESSAGE = (
    "In order to build numpy, you must set minimum ndk api (minapi) to `24`.\n"
)


class NumpyRecipe(MesonRecipe):
    version = "v1.26.5"
    site_packages_name = "numpy"
    url = "git+https://github.com/numpy/numpy"

    # IMPORTANT: ensure a meson-python version that provides the `mesonpy`
    # backend and is compatible with NumPy 1.26.x build requirements.
    hostpython_prerequisites = [
        "Cython>=3.0.6",
        "meson-python>=0.15.0,<0.16.0",
    ]

    extra_build_args = [
        "--no-isolation",
        "--skip-dependency-check",
    ]
    need_stl_shared = True

    def get_recipe_meson_options(self, arch):
        options = super().get_recipe_meson_options(arch)
        options["binaries"]["python"] = self.ctx.python_recipe.python_exe
        options["binaries"]["python3"] = self.ctx.python_recipe.python_exe
        options["properties"]["longdouble_format"] = (
            "IEEE_DOUBLE_LE"
            if arch.arch in ["armeabi-v7a", "x86"]
            else "IEEE_QUAD_LE"
        )
        return options

    def get_recipe_env(self, arch, **kwargs):
        env = super().get_recipe_env(arch, **kwargs)
        env["_PYTHON_HOST_PLATFORM"] = arch.command_prefix
        env["NPY_DISABLE_SVML"] = "1"
        env["TARGET_PYTHON_EXE"] = join(
            Recipe.get_recipe("python3", self.ctx).get_build_dir(arch.arch),
            "android-build",
            "python",
        )
        return env

    def download_if_necessary(self):
        if self.ctx.ndk_api < 24:
            error(NUMPY_NDK_MESSAGE)
            exit(1)
        super().download_if_necessary()

    def build_arch(self, arch):
        super().build_arch(arch)
        # Restore cython version back to the one provided by the p4a recipe
        # after building numpy.
        self.restore_hostpython_prerequisites(["cython"])

    def get_hostrecipe_env(self, arch):
        env = super().get_hostrecipe_env(arch)
        env["RANLIB"] = shutil.which("ranlib")
        return env


recipe = NumpyRecipe()

