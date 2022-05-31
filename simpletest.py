import collections
import inspect
import sys
import os

import bytecode_runner


class TestCaseBytecodeRunner(bytecode_runner.BytecodeRunner):
  CODES = {
    '==': 'was not equal to',
    '>': 'was not greater than',
    '>=': 'was not greater than or equal to',
    '<': 'was not less than',
    '<=': 'was not less than or equal to',
  }

  def __init__(self, func):
    super().__init__(func)
    self.check_count = 0
    self.errors = []

  def checkPass(self):
    self.check_count += 1

  def checkFail(self, message):
    self.check_count += 1
    self.errors.append(
      '%s:%d -- \n\t%s\n' % (
        os.path.relpath(self._filename),
        self._line,
        message,
      )
    )

  def op_IS_OP(self, invert):
    super().op_IS_OP(invert)
    c = self._stack[-1]
    if c.value:
      self.checkPass()
    else:
      self.checkFail(c.name)

  def op_CONTAINS_OP(self, invert):
    super().op_CONTAINS_OP(invert)
    c = self._stack[-1]
    if c.value:
      self.checkPass()
    else:
      self.checkFail(c.name)

  def op_COMPARE_OP(self, i):
    super().op_COMPARE_OP(i)
    c = self._stack[-1]
    left = c.args[0]
    right = c.args[1]
    if c.value:
      self.checkPass()
    else:
      if type(left.value) == list and type(right.value) == list:
        if set(left.value) == set(right.value):
          extra_info = 'lists were equal when order was ignored'
      else:
        extra_info = None
      self.checkFail('%s\n\t  %s\n\t%s%s' % (
          left,
          TestCaseBytecodeRunner.CODES.get(c.action.code, c.action.code),
          right,
          ('\n\t(%s)' % extra_info) if extra_info else '',
        )
      )


def _get_public_routine_names(cls):
  return {
    r[0]
    for r in inspect.getmembers(cls, predicate=inspect.isroutine)
    if not r[0].startswith('_')
  }


def _get_routines_with_filter(x, routine_filter):
  return {
    t[0]
    for t in inspect.getmembers(x, predicate=inspect.isroutine)
    if t[0].startswith(routine_filter)
  }


class TestCaseMeta(type):
  def __new__(cls, name, bases, dct, testing=None):
    routines = _get_public_routine_names(testing) if testing else {'test'}
    routines_untested = routines.copy()
    test_case = super().__new__(cls, name, bases, dct)
    tests = set()
    for r in routines:
      test_routines = _get_routines_with_filter(test_case, r)
      tests.update(test_routines)
      if test_routines:
        routines_untested.remove(r)
    meta_failures = []
    if testing and routines_untested:
      meta_failures.append(
        'Untested routines on `%s`:\n\t- %s' % (
          testing.__name__,
          '\n\t- '.join(routines_untested)
        )
      )
    all_test_routines = _get_public_routine_names(test_case)
    methods_to_ignore = dct.get('IGNORE_METHODS', set())
    for b in bases:
      methods_to_ignore = methods_to_ignore.union(b.__dict__.get('IGNORE_METHODS', set()))
    extra_test_routines = all_test_routines - tests - methods_to_ignore
    if extra_test_routines:
      meta_failures.append(
        'Extra test routines:\n\t- %s' % ('\n\t- '.join(sorted(extra_test_routines)))
      )
    if meta_failures:
      print('Meta Failures for `%s` %s' % (name, '*' * 20))
    for e in meta_failures:
      print('  %s' % e)
    test_case._tests = tests
    if 'TestCase' in {b.__name__ for b in bases}:
      ALL_TEST_CASES[name] = test_case()
    return test_case


ALL_TEST_CASES = {}


def main(runs=1):
  fail_count = 0
  for k in sorted(ALL_TEST_CASES.keys()):
    t = ALL_TEST_CASES[k]
    for _ in range(runs):
      t.run()
    print('%s %s %s' % (
        k,
        'FAILED' if t.failed else 'PASSED',
        '*' * 20
      )
    )
    fail_count += 1 if t.failed else 0
    t.print()
  sys.exit(fail_count)


TestResult = collections.namedtuple('TestResult', ('errors', 'check_count'))

class TestCase(metaclass=TestCaseMeta):
  """Base test case."""
  IGNORE_METHODS = {
    'runTest', 'setUp', 'tearDown', 'setup', 'teardown', 'run', 'print', 'test',
  }

  def __init__(self):
    super().__init__()
    self.runs = []
    self.failed = False

  def setup(self):
    """Called once before each test."""

  def teardown(self):
    """Called once after each test."""

  def run(self):
    run = self.test()
    self.failed = any(len(m) for m in run.values()) or self.failed
    self.runs.append(run)

  def print(self):
    for r, run in enumerate(self.runs):
      if len(self.runs) > 1:
        print('Run %d / %d' % (r + 1, len(self.runs)))
      for k in sorted(run.keys()):
        errors, check_count = run[k]
        results_prev = set()
        for pr in range(r):
          results_prev = results_prev.union(self.runs[pr][k].errors)
        print('%s %s (%d/%d OK) %s\n' % (
            k,
            'FAILED' if len(errors) else 'PASSED',
            check_count - len(errors),
            check_count,
            '*' * 20
          )
        )
        if len(errors):
          unique_errors = [e for e in errors if e not in results_prev]
          repeat_error_count = len(errors) - len(unique_errors)
          if repeat_error_count:
            print('  %d previous errors were repeated\n' % repeat_error_count)
          for e in unique_errors:
            print('  %s' % e)

  def test(self):
    results = {}
    for t in self._tests:
      self.setup()
      f = getattr(self, t)
      bcr = TestCaseBytecodeRunner(f)
      errors = []
      try:
        bcr.run()
      except Exception as e:
        errors.append(e)
      finally:
        errors = bcr.errors + errors
      results[t] = TestResult(errors=errors, check_count=bcr.check_count)
      self.teardown()
    return results
