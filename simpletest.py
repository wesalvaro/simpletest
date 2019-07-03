import dis
from unittest.mock import sentinel


OPS_LOAD = {
  'LOAD_GLOBAL': (lambda i, o: o + [i.argval]),
  'LOAD_FAST': (lambda i, o: o + [i.argval]),
  'LOAD_METHOD': (lambda i, o: o + ['.', i.argval]),
  'LOAD_ATTR': (lambda i, o: o[:-1] + [o[-1] + '.' + i.argval]),
  'LOAD_CONST': (lambda i, o: o + [i.argval]),
}

COMPARISONS = {
  '==': 'to equal',
  'is': 'to be',
  'in': 'to be contained in',
}


def build_arguments(arg_stack, arg_count):
  if not arg_count:
    return arg_stack + ['()']
  arg_list = ['(%s)' % ','.join(repr(a) for a in arg_stack[-arg_count:])]
  return arg_stack[:-arg_count] + arg_list


def compare_op(i, o, nn):
  locals().update(nn)
  left, right = o[-2], o[-1]
  result = eval('%s %s %s' % (left, i.argval, right))
  if not result:
    nice_cmp = COMPARISONS.get(i.argval, i.argval)
    return ['AssertionError("Expected %s %s %s")' % (left, nice_cmp, right,)]
  return [None]


OPS_EVAL = {
  'CALL_FUNCTION': (lambda i, o, nn: build_arguments(o, i.arg)),
  'CALL_METHOD': (lambda i, o, nn: build_arguments(o, i.arg)),
  'COMPARE_OP': compare_op,
}


def store_fast(i, o, nn):
  nn[i.argval] = o.pop()


OPS_META = {
  'STORE_FAST': store_fast,
  'POP_TOP': (lambda i, o, nn: o.pop()),
  'RETURN_VALUE': (lambda i, o, nn: sentinel.DONE),
}


def run(ops, names):
  locals().update(names)
  return eval(''.join(str(o) for o in ops))


def test(f, symbols=None):
  bc = dis.Bytecode(f)
  eval_ops = []
  names = symbols or {}
  errors = []
  line = 0
  filename = bc.codeobj.co_filename
  for i in bc:
    line = i.starts_line if i.starts_line else line
    opname = i.opname
    if opname in OPS_LOAD:
      eval_ops = OPS_LOAD[opname](i, eval_ops)
    elif opname in OPS_EVAL:
      eval_ops = OPS_EVAL[opname](i, eval_ops, names)
      result = run(eval_ops, names)
      if isinstance(result, AssertionError):
        errors.append(("%s:%d" % (filename, line), str(result)))
        result = None
      eval_ops = [result]
    elif opname in OPS_META:
      meta = OPS_META[opname](i, eval_ops, names)
      if meta is sentinel.DONE:
        for err in errors:
          print("%s -- %s" % err)
        if errors:
          return '[!!] Test failed %d comparisons.' % len(errors)
        return '[OK] Pass'
      elif meta:
        raise AssertionError(meta)
    else:
      raise ValueError('Unsupported operation ' + str(i))


class TestCaseMeta(type):
  def __new__(cls, name, bases, dct, symbols=None):
    tests = {k: v for k, v in dct.items() if k.startswith('test')}

    def run_tests(self):
      for k, v in tests.items():
        print(k, test(v, symbols))

    x = super().__new__(cls, name, bases, dct)
    x.run = run_tests
    return x


class TestCase(metaclass=TestCaseMeta):
  """Base test case."""
