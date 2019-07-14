import simpletest
import example
import math


class ExampleTest(simpletest.TestCase, testing=example.Example):
  def setup(self):
    self.ex = example.Example()

  def negate(self):
    ex = self.ex
    ex.negate(True) is False
    ex.negate(False) is not None
    ex.negate(False) is False
    ex.negate(True) is None

  def add5(self):
    ex = self.ex
    ex.add5(1) == 6
    ex.add5(2) == 6
    math.pi > ex.add5(1)
    ex.add5(math.pi) in (4, 5)

  def add5_passes(self):
    self.ex.add5(5) == 10

  def extra_test_method(self):
    """This method is not named correctly for testing example.Example"""


if __name__ == '__main__':
  simpletest.run_all(runs=2)
