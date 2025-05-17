from setuptools import setup, find_packages, Extension
from Cython.Build import cythonize

# run via the command: 'setup.py build_ext --inplace'

extensions = [
    Extension("src_code.market.market", ["src_code/market/market.pyx"])
]

setup(
    ext_modules=cythonize(extensions)
)
