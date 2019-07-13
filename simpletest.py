import dis
from unittest.mock import sentinel
import collections
import types
import inspect
import sys


class Value(object):
  def __init__(self, value, name):
    self.value, self.name = value, name

  def __str__(self):
    if self.name == self.value:
      return str(self.value)
    elif isinstance(self.value, types.ModuleType):
      return str(self.name)
    else:
      return '%s <%s>' % (self.name, self.value)


class Result(object):
  def __init__(self, value, args, action):
    self.value, self.args, self.action = value, args, action

  def __str__(self):
    return '%s(%s) <%s>' % (
      self.action,
      ', '.join(str(a) for a in self.args),
      self.value
    )


Comparison = collections.namedtuple('Comparison', ['code'])


class Method(object):
  def __init__(self, value, name, parent):
    self.value, self.name, self.parent = value, name, parent

  def __str__(self):
    return '%s.%s' % (self.parent.name, self.name,)


class Attr(object):
  def __init__(self, value, name, parent):
    self.value, self.name, self.parent = value, name, parent

  def __str__(self):
    return '%s.%s <%s>' % (self.parent, self.name, self.value)


class BytecodeRunner(object):

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
    self._stack.append(Value(value=self._symbols[i.argval], name=i.argval))

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
    self._symbols[i.argval] = value.value

  def op_POP_TOP(self, i):
    self._stack.pop()

  def op_RETURN_VALUE(self, i):
    self.return_value = self._stack.pop().value

  def op_COMPARE_OP(self, i):
    right = self._stack.pop()
    left = self._stack.pop()
    locals().update(self._symbols)
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
    x = super().__new__(cls, name, bases, dct)
    tests = set()
    for r in routines:
      test_routines = _get_routines_with_filter(x, r)
      tests.update(test_routines)
      if test_routines:
        routines_untested.remove(r)
    meta_failures = []
    if testing and routines_untested:
      meta_failures.append(
        'Untested routines on `%s`: %s' % (
          testing.__name__,
          ', '.join(routines_untested)
        )
      )
    all_test_routines = _get_public_routine_names(x) or set()
    extra_test_routines = all_test_routines - tests - {
      'run', 'setup', 'teardown',
    }
    if extra_test_routines:
      meta_failures.append(
        'Extra test routines on `%s`: %s' % (
          name,
          ', '.join(extra_test_routines)
        )
      )
    x._tests = tests
    x._meta_failures = meta_failures
    return x


class TestCase(metaclass=TestCaseMeta):
  """Base test case."""

  def setup(self):
    """Called once before each test."""

  def teardown(self):
    """Called once after each test."""

  def run(self):
    for e in self._meta_failures:
      print(e)
    failed = 0
    for k in sorted(self._tests):
      self.setup()
      f = getattr(self, k)
      bcr = TestCaseBytecodeRunner(f)
      try:
        bcr.run()
      except Exception as e:
        failed += 1
        print(e)
      self.teardown()
      failed += 1 if bcr.errors else 0
      if failed:
        print('%s FAILED %s\n' % (k, '*' * 20))
        for e in bcr.errors:
          print('  %s' % e)
    sys.exit(failed)
