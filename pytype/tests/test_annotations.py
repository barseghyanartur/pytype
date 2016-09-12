"""Tests for inline annotations."""

import os

from pytype.tests import test_inference


class AnnotationTest(test_inference.InferenceTest):
  """Tests for PEP 484 style inline annotations."""


  def testSimple(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      def bar(p1: file, p2: float) -> int:
        a = ...
        p1.read()
        p2.as_integer_ratio()
        return 1
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      def bar(p1: file, p2: float) -> int
    """)

  def testOnlyAnnotations(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      def bar(p1: str, p2: complex) -> int:
         pass
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      def bar(p1: str, p2: complex) -> int
    """)

  def testDeep(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      def bar(p1: str, p2: complex) -> None:
         pass
    """, deep=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      def bar(p1: str, p2: complex) -> None
    """)

  def testUnion(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      import typing
      def foo(x: typing.Union[int, float], y: int):
        return x + y
    """, deep=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      typing = ...  # type: module
      def foo(x: Union[int, float], y:int) -> Union[int, float]: ...
    """)

  def testCallError(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      s = {1}
      def foo(x: int):
        s.intersection(x)
      foo(3.0)
    """)
    # File "t.py", line 8, in <module>:
    #   Function "foo" was called with the wrong arguments
    #   Expected: (x: int)
    #   Actually passed: (x: float)
    self.assertErrorLogContains(errors, r"line 5.*wrong arguments")

  def testErrorOnAmbiguousArg(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      def f(x: int):
        return x
      def g(y, z):
        if y:
          x = 3
        elif z:
          x = 3j
        else:
          x = "foo"
        f(x)
    """)
    self.assertErrorLogIs(errors,
                          [(11, "wrong-arg-types", "Union.*complex.*str")])

  def testInnerError(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      def foo(x: int):
        return x.upper()
    """)
    # Line 3, in foo:
    #   No attribute 'upper' on int
    self.assertErrorLogContains(errors, r"line 3.*no attribute.*upper")

  def testList(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations

      from typing import List

      def foo(l1: List[int], l2: List[str], b):
        if b:
          x = l1
          y = 3
        else:
          x = l2
          y = "foo"
        x.append(y)
    """, deep=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
        List = ...  # type: Any
        google_type_annotations = ...  # type: __future__._Feature

        def foo(l1: List[int], l2: List[str], b) -> None: ...
    """)

  def testAnalyzeInit(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      from typing import List
      class Foo:
        def f(self, x: List[int]):
          pass
    """, deep=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      List = ...  # type: Any
      class Foo:
        def f(self, x: List[int]) -> None: ...
    """)

  def testStringAnnotation(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      def f(c: "int") -> "None":
        c += 1
        return
    """, deep=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      def f(c: int) -> None: ...
    """)

  def testTypingOnlyImport(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      import typing
      if typing.TYPE_CHECKING:
        import calendar
      # TODO(kramm): should use quotes
      def f(c: "calendar.Calendar") -> int:
        return c.getfirstweekday()
    """, deep=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      typing = ...  # type: module
      calendar = ...  # type: module
      def f(c: calendar.Calendar) -> int: ...
    """)

  def testAmbiguousAnnotation(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      def foo(x: int or float):
        return x
      def foo(x: "int or float"):
        return x
    """)
    self.assertErrorLogIs(errors, {
        (2, "invalid-annotation"),
        (4, "invalid-annotation")})

  def testBadStringAnnotation(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      def foo(x: str()):
        return x
    """)
    self.assertErrorLogIs(errors, {
        (2, "invalid-annotation")})

  def testBadReturn(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      def foo(x: str, y: str) -> int:
        return "foo"
    """)
    self.assertErrorLogIs(errors, {
        (3, "bad-return-type")})

  def testMultipleReturns(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      def foo(x: str, y: str) -> int:
        if x:
          return "foo"
        else:
          return 3j
    """)
    self.assertErrorLogIs(errors, {
        (4, "bad-return-type", r"is str.*should be int"),
        (6, "bad-return-type", r"is complex.*should be int")
    })

  def testAmbiguousReturn(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      def foo(x: str) -> int:
        if x:
          y = "foo"
        else:
          y = 3j
        return y
    """)
    self.assertErrorLogIs(errors, {
        (7, "bad-return-type", r"is Union(?=.*complex).*str.*should be int"),
    })

  def testDefaultReturn(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      class Foo(object):
        def bar(self, x: float, default="") -> str:
          default.upper
          return default
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      class Foo(object):
        def bar(self, x: float, default=...) -> str: ...
    """)

  def testCompatBool(self):
    self.assertNoErrors("""\
      from __future__ import google_type_annotations
      def bar(x: bool) -> bool:
        return None
      bar(None)
    """)

  def testCompatFloat(self):
    self.assertNoErrors("""\
      from __future__ import google_type_annotations
      def bar(x: float) -> float:
        return 1
      bar(42)
    """)

  def testCompatUnicodeStr(self):
    # Use str to be identical in py2 and py3
    self.assertNoErrors("""\
      from __future__ import google_type_annotations
      def bar(x: unicode) -> unicode:
        return str("foo")
      bar(str("bar"))
    """)

  def testCompatUnicodeBytes(self):
    self.assertNoErrors("""\
      from __future__ import google_type_annotations
      def bar(x: unicode) -> unicode:
        return b"foo"
      bar(b"bar")
    """)

  def testCompatUnicodeUnicode(self):
    self.assertNoErrors("""\
      from __future__ import google_type_annotations
      def bar(x: unicode) -> unicode:
        return u"foo"
      bar(u"bar")
    """)

  def testUnsolvable(self):
    self.assertNoCrash("""\
      from __future__ import google_type_annotations
      import unknown_module
      def f(x: unknown_module.Iterable):
        pass
    """)

  def testAny(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      from typing import Any
      def f(x: Any):
        pass
      x = f(3)
    """, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      Any = ...  # type: Any
      def f(x: Any) -> None: ...
      x = ...  # type: None
    """)

  def testDict(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import Dict, List
      def keys(d: Dict[str, int]):
        return
      keys({"foo": 3})
      keys({})  # not allowed
      keys({3: 3})  # not allowed
    """, deep=True, extract_locals=True)
    self.assertErrorLogIs(errors, [
        (6, "wrong-arg-types"),
        (7, "wrong-arg-types"),
    ])

  def testSequence(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import Sequence
      def f(s: Sequence):
        return s
      f([1,2,3])
      f((1,2,3))
      f({1,2,3})
      f(1)
    """, deep=True, extract_locals=True)
    self.assertErrorLogIs(errors, [
        (8, "wrong-arg-types"),
    ])


if __name__ == "__main__":
  test_inference.main()