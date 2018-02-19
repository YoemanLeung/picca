#!/usr/bin/env python

import glob

from setuptools import setup, find_packages

scripts = glob.glob('bin/*')

description = "Package for Igm Cosmological-Correlations Analyses"

version="0.9"
setup(name="picca",
      version=version,
      description=description,
      url="https://github.com/igmhub/picca",
      author="Nicolas Busca et al",
      author_email="ngbusca@lpnhe.in2p3.fr",
      packages=find_packages(),
      package_dir = {'': 'py'},
      install_requires=['future','scipy','numpy','fitsio','numba', 'healpy','iminuit','h5py'],
      test_suite='picca.test.test_cor',
      scripts = scripts
      )

