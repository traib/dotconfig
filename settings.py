import dataclasses
import enum
import os
import platform
import typing
from typing import List, Optional

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))


@dataclasses.dataclass(frozen=True)
class Location:
    save: str
    linux: Optional[str] = None
    darwin: Optional[str] = None
    windows: Optional[str] = None

    def inside_repo(self) -> os.PathLike:
        return os.path.join(SCRIPT_DIR, self.save)

    def outside_repo(self) -> Optional[os.PathLike]:
        load = getattr(self, platform.system().lower())
        return None if not load else os.path.expandvars(load)


class CategoryDescription(typing.NamedTuple):
    locations: List[str]
    after_restore: List[List[str]] = []


class Category(CategoryDescription, enum.Enum):

    VSCODE = CategoryDescription(
        locations=[
            Location(
                # https://code.visualstudio.com/docs/getstarted/settings#_settings-file-locations
                save='Code/User/settings.json',
                linux='$HOME/.config/Code/User/settings.json',
                darwin=
                '$HOME/Library/Application Support/Code/User/settings.json',
                windows='%APPDATA%/Code/User/settings.json'
            ),
        ],
        after_restore=[
            [
                'code', '--install-extension', 'vscodevim.vim',
                '--install-extension', 'ms-python.python'
            ],
        ]
    )


if __name__ == '__main__':
    import argparse
    import contextlib
    import difflib
    import io
    import shutil
    import subprocess

    def categories(names: List[str]) -> List[Category]:
        return list(Category) if not names else [
            Category[name.upper()] for name in names
        ]

    def open_or_empty(file: os.PathLike):
        if not os.path.isfile(file):
            return contextlib.nullcontext(io.StringIO())
        return open(file)

    def backup(args):
        for category in categories(args.categories):
            print()
            print(category)
            print('=' * len(str(category)))

            for location in category.locations:
                src = location.outside_repo()
                dst = location.inside_repo()
                print()
                print('(src="{}",\n dst="{}")'.format(src, dst))

                if args.dry_run or src is None:
                    continue

                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)

    def restore(args):
        for category in categories(args.categories):
            print()
            print(category)
            print('=' * len(str(category)))

            for location in category.locations:
                src = location.inside_repo()
                dst = location.outside_repo()
                print()
                print('(src="{}",\n dst="{}")'.format(src, dst))

                if args.dry_run or dst is None:
                    continue

                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)

            for command in category.after_restore:
                command = [shutil.which(command[0])] + command[1:]
                print()
                print(command)

                if args.dry_run:
                    continue

                print(
                    subprocess.check_output(
                        command, stderr=subprocess.STDOUT, text=True
                    )
                )

    def diff(args):
        for category in categories(args.categories):
            print()
            print(category)
            print('=' * len(str(category)))

            for location in category.locations:
                src = location.inside_repo()
                dst = location.outside_repo()

                if dst is None:
                    continue

                with open_or_empty(src) as src_file:
                    with open_or_empty(dst) as dst_file:
                        print()
                        print(
                            *difflib.unified_diff(
                                src_file.readlines(),
                                dst_file.readlines(),
                                fromfile=src,
                                tofile=dst,
                                n=0
                            )
                        )

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='subcommand', required=True)

    backupparser = subparsers.add_parser('backup')
    backupparser.set_defaults(handler=backup)
    backupparser.add_argument('--dry-run', action='store_true')
    backupparser.add_argument(
        'categories',
        nargs='*',
        choices=[''] + [category.name.lower() for category in Category],
        default=''
    )

    restoreparser = subparsers.add_parser('restore')
    restoreparser.set_defaults(handler=restore)
    restoreparser.add_argument('--dry-run', action='store_true')
    restoreparser.add_argument(
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
