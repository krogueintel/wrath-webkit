# Copyright (c) 2010, Google Inc. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
# copyright notice, this list of conditions and the following disclaimer
# in the documentation and/or other materials provided with the
# distribution.
#     * Neither the name of Google Inc. nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


try:
    import json
except ImportError:
    # python 2.5 compatibility
    import webkitpy.thirdparty.simplejson as json

# FIXME: common should never import from new-run-webkit-tests, one of these files needs to move.
from webkitpy.layout_tests.layout_package import json_results_generator, test_expectations, test_results, test_failures


# These are helper functions for navigating the results json structure.
def for_each_test(tree, handler, prefix=''):
    for key in tree:
        new_prefix = (prefix + '/' + key) if prefix else key
        if 'actual' not in tree[key]:
            for_each_test(tree[key], handler, new_prefix)
        else:
            handler(new_prefix, tree[key])


def result_for_test(tree, test):
    parts = test.split('/')
    for part in parts:
        tree = tree[part]
    return tree


# Wrapper around the dictionaries returned from the json.
# Eventually the .json should just serialize the TestFailure objects
# directly and we won't need this.
class JSONTestResult(object):
    def __init__(self, test_name, result_dict):
        self._test_name = test_name
        self._result_dict = result_dict

    def did_pass(self):
        return test_expectations.PASS in self._actual_as_expectations()

    def _actual_as_expectations(self):
        actual_results = self._result_dict['actual']
        expectations = map(test_expectations.TestExpectations.expectation_from_string, actual_results.split(' '))
        if None in expectations:
            log("Unrecognized actual result in %s" % actual_results)
        return expectations

    def _failure_types_from_actual_result(self, actual):
        # FIXME: There doesn't seem to be a full list of all possible values of
        # 'actual' anywhere.  However JSONLayoutResultsGenerator.FAILURE_TO_CHAR
        # is a useful reference as that's for "old" style results.json files
        if actual == test_expectations.PASS:
            return []
        elif actual == test_expectations.TEXT:
            return [test_failures.FailureTextMismatch()]
        elif actual == test_expectations.IMAGE:
            return [test_failures.FailureImageHashMismatch()]
        elif actual == test_expectations.IMAGE_PLUS_TEXT:
            return [test_failures.FailureImageHashMismatch(), test_failures.FailureTextMismatch()]
        elif actual == test_expectations.AUDIO:
            return [test_failures.FailureAudioMismatch()]
        elif actual == test_expectations.TIMEOUT:
            return [test_failures.FailureTimeout()]
        elif actual == test_expectations.CRASH:
            return [test_failures.FailureCrash()]
        elif actual == test_expectations.MISSING:
            return [test_failures.FailureMissingResult(), test_failures.FailureMissingImageHash(), test_failures.FailureMissingImage()]
        else:
            log("Failed to handle: %s" % self._result_dict['actual'])
            return []

    def _failures(self):
        if self.did_pass():
            return []
        return sum(map(self._failure_types_from_actual_result, self._actual_as_expectations()), [])

    def test_result(self):
        # FIXME: Optionally pull in the test runtime from times_ms.json.
        return test_results.TestResult(self._test_name, self._failures())


class ResultsJSONParser(object):
    """Parse unexpected_results.json files from new-run-webkit-tests
    This will not parse the old results.json format."""

    @classmethod
    def parse_results_json(cls, json_string):
        if not json_results_generator.has_json_wrapper(json_string):
            return None

        content_string = json_results_generator.strip_json_wrapper(json_string)
        json_dict = json.loads(content_string)

        json_results = []
        for_each_test(json_dict['tests'], lambda test, result: json_results.append(JSONTestResult(test, result)))

        # FIXME: What's the short sexy python way to filter None?
        # I would use [foo.bar() for foo in foos if foo.bar()] but bar() is expensive.
        non_passing_results = [result.test_result() for result in json_results if not result.did_pass()]
        return filter(lambda a: a, non_passing_results)
