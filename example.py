class Example(object):
  def __init__(self, *args, **kwargs):
    return super().__init__(*args, **kwargs)

  def negate(self, value):
    return not value

  def add5(self, value):
    return value + 5

  def untested_method(self, value):
    return value + 'ish'
