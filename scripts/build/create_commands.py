#!/usr/bin/env python2
"""
Copy CodeChecker entry point sub-commands.
"""
import argparse
import glob
import json
import logging
import os
import shutil

LOG = logging.getLogger('EntryPoints')

msg_formatter = logging.Formatter('[%(levelname)s] - %(message)s')
log_handler = logging.StreamHandler()
log_handler.setFormatter(msg_formatter)
LOG.setLevel(logging.INFO)
LOG.addHandler(log_handler)


def copy_entry_points(input_dirs, build_dir):
    """
    Copy CodeChecker entry point sub-commands.
    """
    package_root = os.path.join(build_dir, 'CodeChecker')
    package_bin = os.path.join(package_root, 'bin')
    target_cc = os.path.join(package_root, 'cc_bin')

    available_commands = []
    for input_dir in input_dirs:
        for input_file in glob.glob(os.path.join(input_dir, '*')):
            file_name = os.path.basename(input_file)
            if not file_name.endswith(".py"):
                # Non-py files use the environment to appear as python
                # files, they go into the folder in PATH as they are
                # entry points.
                if file_name.startswith("codechecker-"):
                    command_name = file_name.replace("codechecker-", "")
                    available_commands.append(command_name)

                    skip_content = "# DO_NOT_INSTALL_TO_PATH"
                    with open(input_file, 'r') as file:
                        if file.readline().strip() == skip_content:
                            LOG.info("Registering sub-command '%s'",
                                     command_name)
                            # If the file is marked not to install, do not
                            # install it. This happens with entry points
                            # whom should not act as "lowercase" entries,
                            # but the sub-command exists as an available
                            # command.
                            continue

                    LOG.info("Registering sub-command '%s' installed to "
                             "PATH", command_name)
                shutil.copy2(input_file, package_bin)
            else:
                # .py files are Python code that must run in a valid env.
                shutil.copy2(input_file, target_cc)

    available_commands.sort()

    commands_json = os.path.join(target_cc, 'commands.json')
    with open(commands_json, 'w') as commands:
        json.dump(available_commands, commands, sort_keys=True)


if __name__ == "__main__":
    description = '''CodeChecker copy entry point sub-commands'''

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=description)

    parser.add_argument('input',
                        type=str,
                        nargs='+',
                        metavar='folder',
                        help="List of directories which contains CodeChecker "
                              "sub-commands")

    parser.add_argument('-b', '--build-dir',
                        required=True,
                        action='store',
                        dest='build_dir',
                        help="Build directory of the source repository.")

    parser.add_argument('-v', '--verbose',
                        action='store_true',
                        dest='verbose',
                        help="Set verbosity level.")

    args = vars(parser.parse_args())

    if 'verbose' in args and args['verbose']:
        LOG.setLevel(logging.DEBUG)

    if isinstance(args['input'], str):
        args.input = [args.input]

    copy_entry_points(args['input'], args['build_dir'])
