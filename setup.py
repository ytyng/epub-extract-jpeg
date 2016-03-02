#!/usr/bin/env python
# coding: utf-8
from setuptools import setup
from epub_extract_jpeg import __author__, __version__, __license__

setup(
    name='epub-extract-jpeg',
    version=__version__,
    description='Extract comic EPUB pages to Jpeg files.',
    license=__license__,
    author=__author__,
    author_email='ytyng@live.jp',
    url='https://github.com/ytyng/epub-extract-jpeg.git',
    keywords='comic epub extract jpeg',
    packages=['epub_extract_jpeg'],
    install_requires=[],
    entry_points={
        'console_scripts': [
            'epub-extract-jpeg = epub_extract_jpeg.epub_extract_jpeg:main',
        ]
    },
)
