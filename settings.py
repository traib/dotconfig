import sys

sys.dont_write_bytecode = True
assert sys.version_info >= (3, 9)
assert __name__ == '__main__'

import argparse
import contextlib
import difflib
import graphlib
import io
import os
import pathlib
import shutil
import subprocess
import tempfile

from repository import REPOSITORY, Category


def as_categories(
    names: tuple[str], default=tuple(Category)
) -> tuple[Category]:
    return default if not names else tuple(
        Category[name.upper()] for name in names
    )


def topological_sort(names: tuple[str]) -> tuple[Category]:
    visited = set()
    to_visit = list(as_categories(names))
    sorter = graphlib.TopologicalSorter()
    while to_visit:
        category = to_visit.pop()
        prerequisites = as_categories(category.prerequisites, default=())
        visited.add(category)
        sorter.add(category, *prerequisites)
        to_visit.extend(
            prerequisite for prerequisite in prerequisites
            if prerequisite not in visited
        )
    return sorter.static_order()


def open_or_empty(path: pathlib.Path):
    if not path.is_file():
        return contextlib.nullcontext(io.StringIO())
    return open(path)


def mkparents(path: pathlib.Path):
    for parent in reversed(path.parents):
        if not parent.exists():
            parent.mkdir(mode=0o700, parents=False, exist_ok=True)


def symlink_force(src: pathlib.Path, dst: pathlib.Path):
    with tempfile.TemporaryDirectory(dir=REPOSITORY.joinpath('tmp')) as tmp_dir:
        tmp_symlink = pathlib.Path(tmp_dir).joinpath('symlink')
        tmp_symlink.symlink_to(src)
        tmp_symlink.replace(dst)


def cp_force(src: pathlib.Path, dst: pathlib.Path):
    with tempfile.TemporaryDirectory(dir=REPOSITORY.joinpath('tmp')) as tmp_dir:
        tmp_cp = pathlib.Path(tmp_dir).joinpath('cp')
        shutil.copyfile(src, tmp_cp, follow_symlinks=False)
        tmp_cp.replace(dst)


def install(args):
    for category in topological_sort(args.categories):
        if category.is_disabled():
            continue
        print()
        print('=' * len(str(category)))
        print(category)
        print('=' * len(str(category)))

        for command in category.before_install:
            command = command.on_current_platform()
            print()
            print(f'run{command}')

            if args.dry_run:
                continue

            print(
                subprocess.check_output(
                    command, stderr=subprocess.STDOUT, text=True
                )
            )

        for location in category.locations:
            operation = symlink_force if not args.cp else cp_force
            operation_name = 'symlink' if not args.cp else 'cp'

            src = location.inside_repository()
            dst = location.outside_repository()
            if not dst:
                continue

            operation_paths = []

            if src.is_file():
                operation_paths.append((src, dst))

            if src.is_dir():
                for dirpath, _, filenames in os.walk(src):
                    if not filenames:
                        continue

                    for filename in filenames:
                        dir = pathlib.PurePath(dirpath)
                        rel = dir.relative_to(src).joinpath(filename)
                        operation_paths.append(
                            (src.joinpath(rel), dst.joinpath(rel))
                        )

            for src_path, dst_path in operation_paths:
                print()
                print(f"{operation_name}(src='{src_path}', dst='{dst_path}')")

                if args.dry_run:
                    continue

                mkparents(dst_path)
                operation(src_path, dst_path)

        for command in category.after_install:
            command = command.on_current_platform()
            print()
            print(f'run{command}')

            if args.dry_run:
                continue

            print(
                subprocess.check_output(
                    command, stderr=subprocess.STDOUT, text=True
                )
            )


def diff(args):
    for category in topological_sort(args.categories):
        if category.is_disabled():
            continue
        print()
        print('=' * len(str(category)))
        print(category)
        print('=' * len(str(category)))

        for location in category.locations:
            src = location.inside_repository()
            dst = location.outside_repository()
            if not dst:
                continue

            diff_paths = []

            if src.is_file():
                diff_paths.append((src, dst))

            if src.is_dir():
                for dirpath, _, filenames in os.walk(src):
                    if not filenames:
                        continue

                    for filename in filenames:
                        dir = pathlib.PurePath(dirpath)
                        rel = dir.relative_to(src).joinpath(filename)
                        diff_paths.append(
                            (src.joinpath(rel), dst.joinpath(rel))
                        )

            for src_path, dst_path in diff_paths:
                with open_or_empty(src_path) as src_file:
                    with open_or_empty(dst_path) as dst_file:
                        deltas = list(
                            difflib.unified_diff(
                                src_file.readlines(),
                                dst_file.readlines(),
                                fromfile=str(src_path),
                                tofile=str(dst_path),
                                n=0
                            )
                        )
                        if deltas:
                            print()
                            print(''.join(deltas))


parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(dest='subcommand', required=True)

installparser = subparsers.add_parser('install')
installparser.set_defaults(handler=install)
installparser.add_argument('--dry-run', action='store_true')
installparser.add_argument('--cp', action='store_true')
installparser.add_argument(
    'categories',
    nargs='*',
    choices=[''] + [category.name.lower() for category in Category],
    default=''
)

diffparser = subparsers.add_parser('diff')
diffparser.set_defaults(handler=diff)
diffparser.add_argument(
    'categories',
    nargs='*',
    choices=[''] + [category.name.lower() for category in Category],
    default=''
)

args = parser.parse_args()
print(args)
args.handler(args)
