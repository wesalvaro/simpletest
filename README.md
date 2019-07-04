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
pi_test.py:17 -- Expected math.pi <= 3
testPiValue -- Test failed 1 comparison.
```

Ideally, output would also include the actual value:

```sh
pi_test.py:17 -- Expected math.pi <= 3 (but was 3.141592653589793)
testPiValue -- Test failed 1 comparison.
```

## How it works

SimpleTest works by dissasembling the test methods.

Stay with me! The disassembled test method's instructions are then executed
in such a way that we can infer more information from the comparison than we
could from an assert statement. Examining the operands of the comparison and
the code they come from means that we can make more intelligent decisions
about not only the type of comparison, but the code from which it came. This
means more comprehensive output from the most basic of code.
