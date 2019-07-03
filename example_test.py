import simpletest
import example
import math


class ExampleTest(simpletest.TestCase, symbols=globals()):
  def testNegate(self):
    ex = example.Example()
    ex.negate(True) is False
    ex.negate(False) is not None
    ex.negate(False) is False
    ex.negate(True) is None

  def testAdd5(self):
    ex = example.Example()
    ex.add5(1) == 6
    ex.add5(2) == 6

  def testInAttrIneq(self):
    5 in [4, 6]
    4 > math.pi
    math.pi <= 3


if __name__ == '__main__':
  ExampleTest().run()
