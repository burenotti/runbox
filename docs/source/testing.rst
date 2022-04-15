Testing and scoring solutions
=============================

This library is capable of testing a code it gets. So lets test
something!

For example, let's do something simple: FizzBuzz.

The rules are as follows: if the number is divides by 3, we print
``Fizz``, if it's divides by 5 — ``Buzz``. And we print ``FizzBuzz`` if
the number is divides by both.

.. code-block:: python

   n = int(input())

   if n % 3 == 0 and n % 5 == 0:
       print("FizzBuzz")
   elif n % 3 == 0:
       print("Fizz")
   elif n % 5 == 0:
       print("Buzz")
   else:
       print(n)

For testing purposes RunBox provides ``TestCase`` and ``TestSuite``
protocols. You can implement them by yourself, but here we will use a
built-in implementations.

First of all, let's import all the necessary modules.

.. literalinclude:: ../../examples/fizzbuzz.py
    :language: python
    :lines: 1-12


Then, we have to create a ``DockerProfile``. This model contains information
about docker image that will be used:

.. literalinclude:: ../../examples/fizzbuzz.py
    :language: python
    :lines: 14-19

Secondly, we add the ``Limits``:

*  3 seconds for execution
*  64 MB of RAM.

.. literalinclude:: ../../examples/fizzbuzz.py
    :language: python
    :lines: 21-24

Thirdly, we add a ``File`` object, a piece of code that will be executed.

.. literalinclude:: ../../examples/fizzbuzz.py
    :language: python
    :lines: 26-39

Now we are ready to begin.

Let's create a function that will return the result of our test:

.. literalinclude:: ../../examples/fizzbuzz.py
    :language: python
    :lines: 42-67

We also may need to rate (score) a solution. For that RunBox provides
``ScoringSystem`` Protocol. And a ``BaseScoringSystem``, simple
implementation.

``ScoringSystem`` uses two strategies: ``UnitScoringStrategy`` and
``TotalScoringStrategy``. This provides some flexibility in scoring.

Reimplementation of the ``UnitScoringStrategy`` allows you to change
scoring of a single test case. For example, you might want some tests to
weight more than others according to execution time or something else.

Reimplementation of the ``TotalScoringStrategy`` allows you to change
scoring of the whole test suite. For example, changing this strategy you
can fail the whole test suite if a single test fails or set the minimum
total score, that suite should gain.

Let's score our FizzBuzz, using a built-in ``BaseScoringSystem``.

.. literalinclude:: ../../examples/fizzbuzz.py
    :language: python
    :lines: 70-91

Now all that's left is we have to glue everything together with a main function.

.. literalinclude:: ../../examples/fizzbuzz.py
    :language: python
    :lines: 94-111

The final code will look like this.

.. literalinclude:: ../../examples/fizzbuzz.py
    :language: python
