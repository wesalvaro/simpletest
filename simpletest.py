import inspect
import sys

import bytecode_runner


class TestCaseBytecodeRunner(bytecode_runner.BytecodeRunner):
  CODES = {
    '==': 'was not equal to',
    'is': 'was not',
    '>': 'was not greater than',
    '>=': 'was not greater than or equal to',
    '<': 'was not less than',
    '<=': 'was not less than or equal to',
    'in': 'was not contained in',
  }

  def __init__(self, func):
    super().__init__(func)
    self.errors = []

  def op_COMPARE_OP(self, i):
    super().op_COMPARE_OP(i)
    c = self._stack[-1]
    left = c.args[0]
    right = c.args[1]
    if c.value is False:
      self.errors.append(
        '%s:%d -- \n\t%s\n\t  %s\n\t%s\n' % (
          self._filename,
          self._line,
          left,
          TestCaseBytecodeRunner.CODES.get(c.action.code, c.action.code),
          right
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
    extra_test_routines = all_test_routines - tests - dct.get('__IGNORE_METHODS', set())
    if extra_test_routines:
      meta_failures.append(
        'Extra test routines:\n\t- %s' % ('\n\t- '.join(extra_test_routines))
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


def run_all(runs=1):
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


class TestCase(metaclass=TestCaseMeta):
  """Base test case."""
  __IGNORE_METHODS = {
    'run', 'test', 'print', 'setup', 'teardown',
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
        result = run[k]
        results_prev = set()
        for pr in range(r):
          results_prev = results_prev.union(self.runs[pr][k])
        print('%s %s %s\n' % (
            k,
            'FAILED' if len(result) else 'PASSED',
            '*' * 20
          )
        )
        if len(result):
          unique_errors = [e for e in result if e not in results_prev]
          repeat_error_count = len(result) - len(unique_errors)
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
        results[t] = bcr.errors + errors
        self.teardown()
    return results
