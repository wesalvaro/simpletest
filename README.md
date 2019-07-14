# SimpleTest

SimpleTest is currently a proof-of-concept Python testing framework.

SimpleTest is meant to target students, operating on the principle of making
tests extremely easy to author, yet providing comprehensive output when
expectations are missed.

## Example

An example expectation in SimpleTest looks like:

```py
math.pi <= 3
```

Yes, the above snippet works. The current output from this expectation is:

```sh
example_test.py:31 --
	math.pi <3.141592653589793>
	  was not less than
	3
```

A more complex example would be:

```py
x = 5
# (multi-)line gap
x += ex.add5(4)
# (multi-)line gap
x == 13
```

The output for this is:

```sh
example_test.py:26 --
  (5)+(ex.add5(4) <9>) <14>
  	was not equal to
  13
```

## How it works

SimpleTest works by dissasembling the test methods.

Stay with me! The disassembled test method's instructions are then executed
in such a way that we can infer more information from the comparison than we
could from an assert statement. Examining the operands of the comparison and
the code they come from means that we can make more intelligent decisions
about not only the type of comparison, but the code from which it came. This
means more comprehensive output from the most basic of code.
