"""
  This script is to be called from the makefile that builds
  the OpenMDAO docs.

  It does the following:

    1. Open up a sqlite database in which to store the
        results of this script
    2. Discover all of the OpenMDAO unit tests
    3. For each unit test, check to see if the docstring
        has a Features section
    4. The arguments for that section list the features
        that are relevant to the unit test
    5. For each argument, store a record in the database
        with this information:
            method_path
            feature
            title

        The method_path is the dotted path to the unit test method,
            e.g. openmdao.core.tests.test_expl_comp.TestExplCompSimple.test_simple

        The feature is the argument from the Feature section

        The title is the Short summary from the docstring of the unit test

    6. Close the database

    This database will be used later in the doc generating process
        as the feature docs will make use of a custom directive that
        includes the unit test code(s) into the feature doc automatically
"""

import importlib
import inspect
import os
import sqlite3
import subprocess
import tempfile
import textwrap
import unittest

from numpydoc.docscrape import NumpyDocString, Reader, ParseError
from numpydoc.docscrape_sphinx import SphinxDocString
from openmdao.docs.config_params import IGNORE_LIST


# The results of this script will be stored in a sqlite database file
# sqlite_file = 'feature_docs_unit_test_db.sqlite'    # name of the sqlite database file
# table_name = 'feature_unit_tests'   # name of the table to be queried

from openmdao.docs._utils.docutil import remove_docstrings, get_method_body, \
        replace_asserts_with_prints, remove_initial_empty_lines_from_source, \
        get_lines_before_test_cases, sqlite_file, table_name, get_unit_test_source_and_run_outputs

# pylint: disable=C0103

# ------------------------begin monkeypatch-----------------------
# monkeypatch to let our docs include a section called "Features"
#    This new custom section will let unit test developers
#    indicate what features this unit test is relevant to.
# For example,
#
#        Features
#        --------
#        IndepVarComp
#        derivatives
#
# indicates that this unit test is relevant to any feature docs
# that discuss IndepVarComp or derivatives


def __str_SphinxDocString__(self, indent=0, func_role="obj"):
    out = []
    out += self._str_signature()
    out += self._str_index() + ['']
    out += self._str_summary()
    out += self._str_extended_summary()
    out += self._str_param_list('Parameters')
    out += self._str_options('Options')
    out += self._str_returns()
    for param_list in ('Other Parameters', 'Raises', 'Warns'):
        out += self._str_param_list(param_list)
    out += self._str_warnings()
    out += self._str_see_also(func_role)
    out += self._str_section('Notes')
    out += self._str_section('Features')
    out += self._str_references()
    out += self._str_examples()
    for param_list in ('Attributes', 'Methods'):
        out += self._str_member_list(param_list)
    out = self._str_indent(out, indent)
    return '\n'.join(out)


def __init_NumpyDocString__(self, docstring, config={}):
    orig_docstring = docstring
    docstring = textwrap.dedent(docstring).split('\n')

    self._doc = Reader(docstring)
    self._parsed_data = {
        'Signature': '',
        'Summary': [''],
        'Extended Summary': [],
        'Parameters': [],
        'Returns': [],
        'Yields': [],
        'Raises': [],
        'Warns': [],
        'Other Parameters': [],
        'Attributes': [],
        'Methods': [],
        'See Also': [],
        'Notes': [],
        'Features': [],
        'Warnings': [],
        'References': '',
        'Examples': '',
        'index': {}
    }

    try:
        self._parse()
    except ParseError as e:
        e.docstring = orig_docstring
        raise


def __str_NumpyDocString__(self, func_role=''):
    out = []
    out += self._str_signature()
    out += self._str_summary()
    out += self._str_extended_summary()
    for param_list in ('Parameters', 'Returns', 'Yields',
                       'Other Parameters', 'Raises', 'Warns'):
        out += self._str_param_list(param_list)
    out += self._str_section('Warnings')
    out += self._str_see_also(func_role)
    for s in ('Notes', 'References', 'Examples', 'Features'):
        out += self._str_section(s)
    for param_list in ('Attributes', 'Methods'):
        out += self._str_param_list(param_list)
    out += self._str_index()
    return '\n'.join(out)


# Do the actual patch switchover to these local versions
NumpyDocString.__init__ = __init_NumpyDocString__
NumpyDocString.__str__ = __str_NumpyDocString__
SphinxDocString.__str__ = __str_SphinxDocString__
# --------------end monkeypatch---------------------


# remove any existing sqlite database file
try:
    os.remove(sqlite_file)
except OSError:
    pass

# Prepare to write to the sqlite database file
conn = sqlite3.connect(sqlite_file)
cur = conn.cursor()
cur.execute("CREATE TABLE {tn}(method_path TEXT, feature TEXT, title TEXT, \
                unit_test_source TEXT, run_outputs TEXT)".format(tn=table_name))

# Search for all the unit tests
suites = []
for listing in os.listdir(".."):
    if os.path.isdir(os.path.join("..", listing)):
        if listing not in IGNORE_LIST:
            suites.append(unittest.TestLoader().discover(os.path.join('..', listing), pattern="test_*.py"))

for suite in suites:
    for test_file in suite:  # Loop through the TestCases found
        for test_case in test_file:  # Loop though the test methods in the TestCases
            if isinstance(test_case, unittest.suite.TestSuite):
                for test_method in test_case:
                    cls = test_method.__class__
                    module_path = cls.__module__
                    class_name = cls.__name__
                    method_name = test_method._testMethodName
                    method_path = '.'.join([module_path, class_name, method_name])
                    test_doc = getattr(cls, method_name).__doc__
                    if test_doc:
                        test_doc_numpy = NumpyDocString(test_doc)
                        if test_doc_numpy['Features']:
                            for feature in [f.strip() for f in test_doc_numpy['Features']]:
                                title = test_doc_numpy['Summary'][0]
                                unit_test_source, run_outputs, skipped, failed = \
                                    get_unit_test_source_and_run_outputs(method_path)
                                cur.execute(
                                    'insert into {tn} values (?,?,?,?,?)'.format(tn=table_name),
                                    (method_path, feature, title, unit_test_source, run_outputs))

conn.commit()
conn.close()
