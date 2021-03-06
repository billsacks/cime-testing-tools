#!/usr/bin/env python
"""FIXME: A nice python program to clobber all the files created by running the cesm test suite.

Author: Ben Andre <andre@ucar.edu>

"""

from __future__ import print_function

import sys

if sys.hexversion < 0x02070000:
    print(70 * "*")
    print("ERROR: {0} requires python >= 2.7.x. ".format(sys.argv[0]))
    print("It appears that you are running python {0}".format(
        ".".join(str(x) for x in sys.version_info[0:3])))
    print(70 * "*")
    sys.exit(1)

import argparse
import os
import shutil
import traceback

try:
    import lxml.etree as etree
except:
    import xml.etree.ElementTree as etree

if sys.version_info[0] == 2:
    from ConfigParser import SafeConfigParser as config_parser
else:
    from configparser import ConfigParser as config_parser

# -----------------------------------------------------------------------------
#
# User input
#
# -----------------------------------------------------------------------------

def commandline_options():
    """Process the command line arguments.

    """
    parser = argparse.ArgumentParser(
        description='clobber a cesm test suite by removing all files related to the suite.')

    parser.add_argument('--backtrace', action='store_true',
                        help='show exception backtraces as extra debugging '
                        'output')

    parser.add_argument('--debug', action='store_true',
                        help='extra debugging output')

    parser.add_argument('--dry-run', action='store_true',
                        help='just print what would be removed without actually removing files.')

    parser.add_argument('--test-spec', nargs='+', required=True,
                        help='path to test spec file')

    options = parser.parse_args()
    return options


def get_user_consent(test_spec_list):
    """Get explicit user consent to destroy their data!
    """
    print("WARNING: This command is destructive!")
    print("WARNING: It will erase all data associated with the test specifications!")
    print("WARNING: It also has the potential to remove other data you care about if something goes wrong.")
    for spec in test_spec_list:
        print("    {0}".format(spec))

    expected = 'destroy'
    proceed = raw_input("\n\nType '{0}' to proceed : ".format(expected))
    if proceed != expected:
        raise RuntimeError("You typed '{0}'. Expected '{1}'. Exiting"
                           " without removing data.".format(proceed, expected))

    clobber_str = 'clobber'
    print("Test root directories may contain log files, result summaries and other useful information.")
    no_interaction = raw_input("Type '{0}' to remove all test roots without further interaction : ".format(clobber_str))
    clobber = False
    if no_interaction == clobber_str:
        clobber = True
    return clobber

# -----------------------------------------------------------------------------
#
# work functions
#
# -----------------------------------------------------------------------------
def read_test_spec_xml(test_spec_filename, debug):
    """Note, assuming that each test spec has a single test list.
    """
    if debug:
        print("Extracting test data from testspec file...")
    filename = os.path.abspath(test_spec_filename)
    if os.path.isfile(filename):
        if debug:
            print("Reading file: {0}".format(filename))
        xml_tree = etree.parse(filename)
    else:
        raise RuntimeError(
            "ERROR: test spec xml file does not exist: {0}".format(test_spec_filename))

    return xml_tree.getroot()


def clobber_test_spec(test_spec_filename, debug, dry_run):
    """
    """
    test_spec = read_test_spec_xml(test_spec_filename, debug)

    test_root = test_spec.findall('./testroot')[0].text

    # FIXME(bja, 20150318) Talk to Jay. Hard coding the scratch
    # directory for yellowstone at the moment because it isn't in the
    # test spec.
    user = os.environ["USER"]
    scratch_dir = '/glade/scratch/{0}'.format(user)
    archive_root = os.path.join(scratch_dir, 'archive')
    archive_locked_root = os.path.join(scratch_dir, 'archive.locked')

    # summarize info:
    print("Clobbering test spec : {0}".format(test_spec_filename))
    if debug:
        print("  test root : {0}".format(test_root))
        print("  scratch dir : {0}".format(scratch_dir))

    sharedlibroot = test_spec.findall("./sharedlibroot")[0].text
    # FIXME(bja, 201503) Talk to Jay. Why isn't this expanded in the
    # test spec? it is very specific and doesn't benefit from
    # remaining an env variable....
    sharedlibroot = sharedlibroot.replace('$USER', user)
    if debug:
        print("  sharedlibroot : {0}".format(sharedlibroot))
    if not dry_run:
        shutil.rmtree(sharedlibroot, ignore_errors=True)

    testlist = test_spec.findall("./test")

    if debug:
        print("  case, build and archive directories:")
    for test in testlist:
        case = test.attrib["case"]
        if debug:
            print("  Clobbering : {0}".format(case))

        case_dir = [ os.path.join(test_root, case) ]
        runbld_dir = [ os.path.join(scratch_dir, case) ]
        archive_dir = [ os.path.join(archive_root, case) ]
        archive_locked_dir = [ os.path.join(archive_locked_root, case) ]

        ref_cases = ["ref1", "ref2"]
        for ref in ref_cases:
            if os.path.isdir(os.path.join(test_root, "{0}.{1}".format(case, ref))):
                case_dir.append(os.path.join(test_root, "{0}.{1}".format(case, ref)))
                runbld_dir.append(os.path.join(scratch_dir, "{0}.{1}".format(case, ref)))
                archive_dir.append(os.path.join(archive_root, "{0}.{1}".format(case, ref)))
                archive_locked_dir.append(os.path.join(archive_locked_root, "{0}.{1}".format(case, ref)))


        if debug:
            print("    case_dir : {0}".format(case_dir))
            print("    runbld_dir : {0}".format(runbld_dir))
            print("    archive_dir : {0}".format(archive_dir))
            print("    archive_locked_dir : {0}".format(archive_locked_dir))

        if not dry_run:
            clobber_tree(case_dir)
            clobber_tree(runbld_dir)
            clobber_tree(archive_dir)
            clobber_tree(archive_locked_dir)

    print('')
    if debug:
        print("    test spec xml : {0}".format(test_spec_filename))
    else:
        os.remove(test_spec_filename)

    return test_root


def clobber_tree(directory_list):
    """
    """
    for directory in directory_list:
        try:
            shutil.rmtree(directory, ignore_errors=True)
            print('.', end='')
        except OSError:
            print('E', end='')
    sys.stdout.flush()


def clobber_test_roots(test_root_list, clobber, debug, dry_run):
    """Accept a list of test roots, find the unique roots and ask the user
    if they should be removed.

    """

    print("Clobbering testroots.")

    test_roots = set(test_root_list)
    for test_root in test_roots:
        print("    testroot : {0}".format(test_root))
        if not dry_run:
            try:
                os.rmdir(test_root)
            except OSError:
                if clobber:
                    shutil.rmtree(test_root, ignore_errors=True)
                else:
                    print("WARNING: Could not remove testroot because it is not empty!")
                    print("WARNING: remaining filse:")
                    contents = os.listdir(test_root)
                    for f in contents:
                        print("WARNING:    {0}".format(f))
                    expected = 'remove'
                    proceed = raw_input("\n\nType '{0}' to proceed : ".format(expected))
                    if proceed != expected:
                        print("You typed '{0}'. Expected '{1}'. Not removing testroot.".format(proceed, expected))
                    else:
                        shutil.rmtree(test_root, ignore_errors=True)

    return 0

# -----------------------------------------------------------------------------
#
# main
#
# -----------------------------------------------------------------------------

def main(options):
    clobber = get_user_consent(options.test_spec)
    test_root_list = []
    for test_spec in options.test_spec:
        test_spec_filename = os.path.abspath(test_spec)
        test_root = clobber_test_spec(test_spec_filename, options.debug, options.dry_run)
        test_root_list.append(test_root)

    clobber_test_roots(test_root_list, clobber, options.debug, options.dry_run)

if __name__ == "__main__":
    options = commandline_options()
    try:
        status = main(options)
        sys.exit(status)
    except Exception as error:
        print(str(error))
        if options.backtrace:
            traceback.print_exc()
        sys.exit(1)
