#!/usr/bin/env python3
import argparse
import shutil
from pathlib import Path


DEFAULT_PATHS = [
    Path('output_test'),
    Path('output_small'),
    Path('.pytest_cache'),
]

DEFAULT_FILES = [
    Path('test_new_link_format.py'),
    Path('test_link_fixing.py'),
]


def main():
    parser = argparse.ArgumentParser(description='Clean outdated test artifacts and temporary outputs.')
    parser.add_argument('--apply', action='store_true', help='Actually delete files/directories. Default is dry-run.')
    parser.add_argument('--paths', nargs='*', help='Additional paths to remove.')
    parser.add_argument('--files', nargs='*', help='Additional files to remove.')
    args = parser.parse_args()

    targets = list(DEFAULT_PATHS)
    if args.paths:
        targets.extend(Path(p) for p in args.paths)

    files = list(DEFAULT_FILES)
    if args.files:
        files.extend(Path(f) for f in args.files)

    removed = []
    skipped = []

    for p in targets:
        if p.exists():
            if args.apply:
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                removed.append(str(p))
            else:
                skipped.append(str(p))

    for f in files:
        if f.exists():
            if args.apply:
                f.unlink()
                removed.append(str(f))
            else:
                skipped.append(str(f))

    if args.apply:
        if removed:
            print('Removed:')
            for r in removed:
                print('  -', r)
        else:
            print('Nothing to remove.')
    else:
        if skipped:
            print('Dry-run. Would remove:')
            for s in skipped:
                print('  -', s)
        else:
            print('Dry-run. Nothing to remove.')


if __name__ == '__main__':
    main()

