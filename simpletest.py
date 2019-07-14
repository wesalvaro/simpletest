import dis
from unittest.mock import sentinel
import collections
import types
import inspect
import sys


class StackObject(object):
  """Object to store on the stack."""


class Value(StackObject):
  def __init__(self, value, name):
    self.value, self.name = value, name

  def __str__(self):
    if self.name == self.value:
      return str(self.value)
    elif isinstance(self.value, types.ModuleType):
      return str(self.name)
    else:
      return '%s <%s>' % (self.name, self.value)


class Result(StackObject):
  def __init__(self, value, args, action):
    self.value, self.args, self.action = value, args, action

  def __str__(self):
    return '%s(%s) <%s>' % (
      self.action,
      ', '.join(str(a) for a in self.args),
      self.value
    )


Comparison = collections.namedtuple('Comparison', ['code'])


class Method(StackObject):
  def __init__(self, value, name, parent):
    self.value, self.name, self.parent = value, name, parent

  def __str__(self):
    return '%s.%s' % (self.parent.name, self.name,)


class Attr(StackObject):
  def __init__(self, value, name, parent):
    self.value, self.name, self.parent = value, name, parent

  def __str__(self):
    return '%s.%s <%s>' % (self.parent, self.name, self.value)


class BytecodeRunner(object):
  """Executes a function's disassembled bytecode instructions.

  See: https://docs.python.org/2.4/lib/bytecodes.html
  """

  def __init__(self, func):
    bc = dis.Bytecode(func)
    self._instructions = (i for i in bc)
    self._filename = bc.codeobj.co_filename
    self._line = bc.first_line
    self._symbols = {}
    self._stack = []
    self._symbols.update(func.__globals__)
    if getattr(func, '__self__', None):
      self._symbols.update({'self': func.__self__})
    self.return_value = sentinel.NOT_RUN

  def run(self):
    for i in self._instructions:
      self._line = i.starts_line if i.starts_line else self._line
      #print(i)
      op = i.opname
      getattr(self, 'op_' + op)(i)
      #print(self._stack)
    return self.return_value

  def op_LOAD_GLOBAL(self, i):
    self._stack.append(Value(value=self._symbols[i.argval], name=i.argval))

  def op_LOAD_FAST(self, i):
    value = self._symbols[i.argval]
    if not isinstance(value, StackObject):
      value = Value(value=value, name=i.argval)
    self._stack.append(value)

  def op_LOAD_METHOD(self, i):
    parent = self._stack.pop()
    self._stack.append(
      Method(
        value=getattr(parent.value, i.argval),
        name=i.argval,
        parent=parent
      )
    )

  def op_LOAD_ATTR(self, i):
    parent = self._stack.pop()
    self._stack.append(
      Attr(value=getattr(parent.value, i.argval), name=i.argval, parent=parent)
    )

  def op_LOAD_CONST(self, i):
    self._stack.append(Value(value=i.argval, name=i.argval))

  def _get_args(self, arg_count):
    if arg_count == 0:
      args = []
    else:
      args = self._stack[-arg_count:]
      self._stack = self._stack[:-arg_count]
    return args

  def op_CALL_FUNCTION(self, i):
    args = self._get_args(i.arg)
    func = self._stack.pop()
    self._stack.append(
      Result(
        value=func.value(*[a.value for a in args]),
        args=args,
        action=func
      )
    )

  def op_CALL_METHOD(self, i):
    args = self._get_args(i.arg)
    method = self._stack.pop()
    self._stack.append(
      Result(
        value=method.value(*[a.value for a in args]),
        args=args,
        action=method
      )
    )

  def op_STORE_FAST(self, i):
    value = self._stack.pop()
    self._symbols[i.argval] = value

  def op_POP_TOP(self, i):
    self._stack.pop()

  def op_ROT_TWO(self, i):
    tos = self._stack.pop()
    tos1 = self._stack.pop()
    self._stack.append(tos, tos1)

  def op_ROT_THREE(self, i):
    tos = self._stack.pop()
    tos1 = self._stack.pop()
    tos2 = self._stack.pop()
    self._stack.append(tos, tos2, tos1)

  def op_ROT_FOUR(self, i):
    tos = self._stack.pop()
    tos1 = self._stack.pop()
    tos2 = self._stack.pop()
    tos3 = self._stack.pop()
    self._stack.append(tos, tos3, tos2, tos1)

  def op_DUP_TOP(self, i):
    self._stack.append(self._stack[-1])

  def _binary_op(self, op_func, op_symbol, op_symbol_end=''):
    tos = self._stack.pop()
    tos1 = self._stack.pop()
    self._stack.append(Value(
      value=op_func(tos1.value, tos.value),
      name='(%s)%s(%s)%s' % (tos1, op_symbol, tos, op_symbol_end)
    ))

  def op_BINARY_POWER(self, i):
    self._binary_op(lambda l, r: l**r, '**')

  def op_BINARY_MULTIPLY(self, i):
    self._binary_op(lambda l, r: l * r, '*')

  def op_BINARY_DIVIDE(self, i):
    raise NotImplementedError('Only true divide is supported')

  def op_BINARY_FLOOR_DIVIDE(self, i):
    self._binary_op(lambda l, r: l // r, '//')

  def op_BINARY_TRUE_DIVIDE(self, i):
    self._binary_op(lambda l, r: l / r, '/')

  def op_BINARY_MODULO(self, i):
    self._binary_op(lambda l, r: l % r, '%')

  def op_BINARY_ADD(self, i):
    self._binary_op(lambda l, r: l + r, '+')

  def op_BINARY_SUBTRACT(self, i):
    self._binary_op(lambda l, r: l - r, '-')

  def op_BINARY_SUBSCR(self, i):
    self._binary_op(lambda l, r: l[r], '[', op_symbol_end=']')

  def op_BINARY_LSHIFT(self, i):
    self._binary_op(lambda l, r: l << r, '')

  def op_BINARY_RSHIFT(self, i):
    self._binary_op(lambda l, r: l >> r, '')

  def op_BINARY_AND(self, i):
    self._binary_op(lambda l, r: l & r, '')

  def op_BINARY_XOR(self, i):
    self._binary_op(lambda l, r: l ^ r, '')

  def op_BINARY_OR(self, i):
    self._binary_op(lambda l, r: l | r, '')

  def op_INPLACE_POWER(self, i):
    self.op_BINARY_POWER(i)

  def op_INPLACE_MULTIPLY(self, i):
    self.op_BINARY_MULTIPLY(i)

  def op_INPLACE_DIVIDE(self, i):
    self.op_BINARY_DIVIDE(i)

  def op_INPLACE_FLOOR_DIVIDE(self, i):
    self.op_BINARY_FLOOR_DIVIDE(i)

  def op_INPLACE_TRUE_DIVIDE(self, i):
    self.op_BINARY_TRUE_DIVIDE(i)

  def op_INPLACE_MODULO(self, i):
    self.op_BINARY_MODULO(i)

  def op_INPLACE_ADD(self, i):
    self.op_BINARY_ADD(i)

  def op_INPLACE_SUBTRACT(self, i):
    self.op_BINARY_SUBTRACT(i)

  def op_INPLACE_LSHIFT(self, i):
    self.op_BINARY_LSHIFT(i)

  def op_INPLACE_RSHIFT(self, i):
    self.op_BINARY_RSHIFT(i)

  def op_INPLACE_AND(self, i):
    self.op_BINARY_AND(i)

  def op_INPLACE_XOR(self, i):
    self.op_BINARY_XOR(i)

  def op_INPLACE_OR(self, i):
    self.op_BINARY_OR(i)

  def op_RETURN_VALUE(self, i):
    self.return_value = self._stack.pop().value

  def op_COMPARE_OP(self, i):
    right = self._stack.pop()
    left = self._stack.pop()
    comparisons = {
      '==': lambda left, right: left == right,
      'is': lambda left, right: left is right,
      'is not': lambda left, right: left is not right,
      'in': lambda left, right: left in right,
      '>': lambda left, right: left > right,
      '>=': lambda left, right: left >= right,
      '<': lambda left, right: left < right,
      '<=': lambda left, right: left <= right,
    }
    value = comparisons[i.argval](left.value, right.value)
    self._stack.append(
      Result(
        value=value,
        args=(left, right),
        action=Comparison(code=i.argval)
      )
    )


class TestCaseBytecodeRunner(BytecodeRunner):
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
    extra_test_routines = all_test_routines - tests - {
      'run', 'test', 'print', 'setup', 'teardown',
    }
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
