import dataclasses
import enum
import os
import platform
import shutil
import sys
from typing import NamedTuple, Optional

assert sys.version_info >= (3, 9)

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))


@dataclasses.dataclass(frozen=True)
class Location:
    save: str
    linux: Optional[str] = None
    darwin: Optional[str] = None
    windows: Optional[str] = None

    def inside_repository(self) -> os.PathLike:
        assert self.save != ''
        return os.path.join(SCRIPT_DIR, self.save)

    def outside_repository(self) -> Optional[os.PathLike]:
        load = getattr(self, platform.system().lower())
        return None if not load else os.path.expandvars(load)


@dataclasses.dataclass(frozen=True)
class Command:
    args: tuple[str]

    def __init__(self, *args):
        object.__setattr__(self, 'args', args)

    def on_current_platform(self) -> tuple[str]:
        assert len(self.args) > 0
        return (shutil.which(self.args[0]),) + self.args[1:]


class CategoryDescription(NamedTuple):
    locations: tuple[Location]
    after_restore: tuple[Command] = ()

    def is_not_enabled(self) -> bool:
        return all(
            not location.outside_repository() for location in self.locations
        )


class Category(CategoryDescription, enum.Enum):

    VSCODE = CategoryDescription(
        locations=(
            Location(
                # https://code.visualstudio.com/docs/getstarted/settings#_settings-file-locations
                save='Code/User/settings.json',
                linux='$HOME/.config/Code/User/settings.json',
                darwin=
                '$HOME/Library/Application Support/Code/User/settings.json',
                windows='%APPDATA%/Code/User/settings.json'
            ),
        ),
        after_restore=(
            Command(
                'code', '--install-extension', 'vscodevim.vim',
                '--install-extension', 'ms-python.python'
            ),
        )
    )


if __name__ == '__main__':
    import argparse
    import contextlib
    import difflib
    import io
    import subprocess

    def categories(names: tuple[str]) -> tuple[Category]:
        return tuple(Category) if not names else (
            Category[name.upper()] for name in names
        )

    def open_or_empty(file: os.PathLike):
        if not os.path.isfile(file):
            return contextlib.nullcontext(io.StringIO())
        return open(file)

    def backup(args):
        for category in categories(args.categories):
            if category.is_not_enabled():
                continue
            print()
            print(category)
            print('=' * len(str(category)))

            for location in category.locations:
                src = location.outside_repository()
                dst = location.inside_repository()
                if not src:
                    continue
                print()
                print('(src="{}",\n dst="{}")'.format(src, dst))

                if args.dry_run:
                    continue

                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)

    def restore(args):
        for category in categories(args.categories):
            if category.is_not_enabled():
                continue
            print()
            print(category)
            print('=' * len(str(category)))

            for location in category.locations:
                src = location.inside_repository()
                dst = location.outside_repository()
                if not dst:
                    continue
                print()
                print('(src="{}",\n dst="{}")'.format(src, dst))

                if args.dry_run:
                    continue

                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)

            for command in category.after_restore:
                command = command.on_current_platform()
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
            if category.is_not_enabled():
                continue
            print()
            print(category)
            print('=' * len(str(category)))

            for location in category.locations:
                src = location.inside_repository()
                dst = location.outside_repository()
                if not dst:
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
