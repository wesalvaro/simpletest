from unittest.mock import sentinel
import collections
import dis
import types


class StackObject(object):
  """Object to store on the stack."""


def is_printable(obj):
  return isinstance(obj, (int, str, float, complex, tuple, list, dict, set, StackObject))


class Value(StackObject):
  def __init__(self, value, name):
    self.value, self.name = value, name

  def __str__(self):
    if self.name == self.value:
      return str(self.value)
    elif isinstance(self.value, types.ModuleType):
      return str(self.name)
    elif is_printable(self.value):
      return '%s=%s' % (self.value, self.name)
    else:
      return str(self.name)

  def __repr__(self):
    return "Value=" + str(self)


class Result(StackObject):
  def __init__(self, value, args, action):
    self.value, self.args, self.action = value, args, action

  def __str__(self):
    if is_printable(self.value):
      return '%s=%s(%s)' % (
        self.value,
        self.action,
        ', '.join(str(a) for a in self.args),
      )
    else:
      return '%s(%s)' % (self.action, ', '.join(str(a) for a in self.args))


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
    if (is_printable(self.value)):
      return '%s=%s.%s' % (self.value, self.parent, self.name)
    else:
      return '%s.%s' % (self.parent, self.name)


class BytecodeRunner(object):
  """Executes a function's disassembled bytecode instructions.

  See: https://docs.python.org/2.4/lib/bytecodes.html
  """

  def __init__(self, func, context=None):
    bc = dis.Bytecode(func)
    self._instructions = (i for i in bc)
    self._filename = bc.codeobj.co_filename
    self._line = bc.first_line
    self._symbols = {}
    self._stack = []
    self._symbols.update(func.__globals__)
    if hasattr(func, '__self__'):
      self._symbols.update({'self': func.__self__})
    elif context:
      self._symbols.update({'self': context})
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

  def _build_iterable(self, iter_func, iter_size, symbol_start, symbol_end):
    iter_values = self._get_args(iter_size)
    all_same = all(str(v.value) == str(v) for v in iter_values)
    iter_result = iter_func(v.value for v in iter_values)
    iter_name = iter_result if all_same else '%s%s%s' % (
      symbol_start,
      ', '.join(str(v) for v in iter_values),
      symbol_end,
    )
    self._stack.append(Value(value=iter_result, name=iter_name))

  def op_BUILD_LIST(self, i):
    self._build_iterable(list, i.arg, '[', ']')

  def op_BUILD_TUPLE(self, i):
    self._build_iterable(tuple, i.arg, '(', ')')

  def op_BUILD_SET(self, i):
    self._build_iterable(set, i.arg, '{', '}')

  def op_IS_OP(self, invert):
    if invert.arg:
      func = lambda x, y: x is not y
      negate = 'not '
    else:
      func = lambda x, y: x is y
      negate = ''
    self._binary_op(func, ' is ' + negate)

  def op_CONTAINS_OP(self, invert):
    if invert.arg:
      func = lambda x, y: x not in y
      negate = ' not'
    else:
      func = lambda x, y: x in y
      negate = ''
    self._binary_op(func, negate + ' in ')

  def op_COMPARE_OP(self, i):
    right = self._stack.pop()
    left = self._stack.pop()
    comparisons = {
      '==': lambda left, right: left == right,
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
