#!/usr/bin/env python
"""
    ..__main__.py
    ~~~~~~~~~~~~~~~~
    AlphaPept command line interface
    :authors: Maximilian Thomas Strauss
    :copyright: Copyright (c) 2020 Mann Labs
"""


with open("alphapept/__init__.py") as version_file:
    VERSION_NO = version_file.read().strip().split('__version__ = ')[1][1:-1]

COPYRIGHT = "2020 Mann Labs"
URL = "https://github.com/MannLabs/alphapept"

import sys
import os

def _run_alphapept(args):
    from runner import run_alphapept
    from settings import load_settings

    if os.path.isfile(args.settings):
        _settings = load_settings(args.settings)
        run_alphapept(_settings)

def _convert(args):
    from io import raw_to_npz
    if os.path.isfile(args.rawfile):
        abundant = args.abundant
        settings = {}
        settings['raw'] = {}
        settings['raw']['most_abundant'] = abundant
        to_process = (args.rawfile, settings)
        raw_to_npz(to_process)

def _database(args):
    raise NotImplementedError

def _features(args):
    raise NotImplementedError

def _search(args):
    raise NotImplementedError

def main():

    import argparse

    # Main parser
    parser = argparse.ArgumentParser("alphapept")
    subparsers = parser.add_subparsers(dest="command")

    workflow_parser = subparsers.add_parser("workflow", help="Process files with alphapept using a settings file.")
    workflow_parser.add_argument("settings", help=("Path to settings file"))

    gui_parser = subparsers.add_parser("gui", help="Open the AlphaPept GUI.")

    convert_parser = subparsers.add_parser('convert', help='Perform file conversion on a raw file for AlphaPept.')
    convert_parser.add_argument("rawfile", help=("Path to rawfile"))
    convert_parser.add_argument(
        "-a",
        "--abundant",
        type=int,
        default=400,
        help=(
            "Number of most abundant peaks to keep. (Default = 400) "
        ),
    )

    database_parser = subparsers.add_parser('database', help='Create a AlphaPept compatible databse from a FASTA file.')

    database_parser.add_argument("fastafile", help=("Path to FASTA file."))
    database_parser.add_argument(
        "-a",
        "--abundant",
        type=int,
        default=400,
        help=(
            "Number of most abundant peaks to keep. (Default = 400) "
        ),
    )

    feature_finder_parser = subparsers.add_parser('features', help='Find features on a specific file.')
    search_parser = subparsers.add_parser('search', help='Search a converted raw file against a AlphaPept compatible database.')
# link parser

    print("\n")
    print(r"     ___    __      __          ____             __ ")
    print(r"    /   |  / /___  / /_  ____ _/ __ \___  ____  / /_")
    print(r"   / /| | / / __ \/ __ \/ __ \/ /_/ / _ \/ __ \/ __/")
    print(r"  / ___ |/ / /_/ / / / / /_/ / ____/  __/ /_/ / /_  ")
    print(r" /_/  |_/_/ .___/_/ /_/\__,_/_/    \___/ .___/\__/  ")
    print(r"         /_/                          /_/           ")
    print("\n")
    print(URL)
    print('{} \t {}'.format(COPYRIGHT, VERSION_NO))

    args = parser.parse_args()
    if args.command:

        if args.command == "workflow_parser":
            if args.settings:
                _run_alphapept(args)

        if args.command == "gui":
            print('Launching GUI')
            from .gui import alphapept as _alphapept
            _alphapept.main()

        if args.command == "convert":
            print('Convert')
            _convert(args)

        if args.command == "database":
            _database(args)

        if args.command == "features":
            _features(args)

        if args.command == "search":
            _search(args)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()