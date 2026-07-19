# Local override of python-for-android tokenizers recipe.
#
# Fix for build failures like:
#   BackendUnavailable: Cannot import 'maturin'
#
# tokenizers uses the `maturin` PEP517 backend. In some p4a environments,
# python-build isolation env creation can fail to make the backend importable.
# We disable build isolation and install maturin into hostpython prerequisites.

from __future__ import annotations

import os
import shutil

from pythonforandroid.recipe import RustCompiledComponentsRecipe


class TokenizersRecipe(RustCompiledComponentsRecipe):
    name = "tokenizers"
    version = "0.22.1"
    url = "https://github.com/huggingface/tokenizers/archive/refs/tags/v{version}.tar.gz"
    sha512sum = "1a25ee6b218232112f10bc1e082e71ed1960ab7fa62c7341b38cc5f5dc0a735cf35b3e90d4a1c1cc0aedb7c198182c2e559662459a668a2fef4e633096a1cccc"

    depends = []

    # NOTE:
    # The upstream p4a recipe applies patches to the *repo layout* version of
    # tokenizers (bindings/python/... etc). However the source we get here is
    # already in a python-package layout (pyproject.toml + py_src at repo root),
    # and after a failed build the directory can be left transformed.
    #
    # To keep rebuilds robust, we do not apply patches at all.
    patches = []

    # Ensure maturin backend is importable without build isolation.
    hostpython_prerequisites = [
        "maturin>=1.0,<2.0",
        "setuptools",
        "wheel",
    ]

    # Pass through to `python -m build ...`
    extra_build_args = [
        "--no-isolation",
        "--skip-dependency-check",
    ]

    def build_arch(self, arch):
        build_dir = self.get_build_dir(arch.arch)

        # Some tokenizers source tarballs (and/or prior failed builds) already
        # have a python-package layout at repo root (pyproject.toml + py_src).
        #
        # If we still have the repo layout, transform it to the python-package
        # layout (like the upstream p4a recipe).
        python_dir = os.path.join(build_dir, "bindings", "python")
        has_repo_layout = os.path.exists(python_dir)

        if has_repo_layout:
            tmp_tokenizer_dir = os.path.abspath(
                os.path.join(build_dir, "..", "temp_tokenizer")
            )
            tmp_tokenizer_dir_base = os.path.join(tmp_tokenizer_dir, "tokenizers")
            base_tokenizers = os.path.join(build_dir, "tokenizers")

            shutil.copytree(python_dir, tmp_tokenizer_dir, dirs_exist_ok=True)
            shutil.copytree(base_tokenizers, tmp_tokenizer_dir_base, dirs_exist_ok=True)
            shutil.rmtree(build_dir)
            shutil.copytree(tmp_tokenizer_dir, build_dir, dirs_exist_ok=True)
            shutil.rmtree(tmp_tokenizer_dir)

        if not os.path.exists(os.path.join(build_dir, "pyproject.toml")):
            raise FileNotFoundError(
                f"pyproject.toml not found in {build_dir} (unexpected tokenizers layout)"
            )

        # In python-package layout, Cargo.toml must refer to the copied Rust
        # sources as ./tokenizers rather than ../../tokenizers.
        #
        # Also disable PyO3 abi3 mode for Android builds.
        #
        # tokenizers 0.22.x enables:
        #   pyo3 = { ..., features = ["abi3", "abi3-py39", "py-clone"] }
        # which produces tokenizers.abi3.so. On python-for-android this can
        # fail at runtime with dlopen errors such as:
        #   cannot locate symbol "Pyexc_exception"
        # Build against the exact target Python instead of the stable ABI.
        cargo_toml = os.path.join(build_dir, "Cargo.toml")
        if os.path.exists(cargo_toml):
            with open(cargo_toml, "r", encoding="utf-8") as f:
                cargo_text = f.read()
            cargo_text = cargo_text.replace(
                'path = "../../tokenizers"',
                'path = "./tokenizers"',
            )
            cargo_text = cargo_text.replace(
                'pyo3 = { version = "0.25", features = ["abi3", "abi3-py39", "py-clone"] }',
                'pyo3 = { version = "0.25", features = ["py-clone"] }',
            )
            with open(cargo_toml, "w", encoding="utf-8") as f:
                f.write(cargo_text)

        super().build_arch(arch)


recipe = TokenizersRecipe()
