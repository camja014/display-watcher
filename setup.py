#!/usr/bin/env python3

from distutils.core import setup

setup(
    name="display-watcher",
    version="1.0",
    description="Executes a command on display state change.",
    author="Cameron Ackerman",
    author_email="cameron@cackerman.dev",
    url="https://github.com/camja014/display-watcher",
    packages=["display_watcher"],
    entry_points={
        "console_scripts": [
            "display-watcher=display_watcher.display_watcher:main",
        ],
    },
)
