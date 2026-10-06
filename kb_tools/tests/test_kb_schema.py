"""Unit tests for ``kb_schema.number_token``, the register's one number reader."""

import unittest

from kb_tools import kb_schema


class TestNumberToken(unittest.TestCase):
    def test_reads_a_leading_float_literal(self):
        for text, expected in (
            ("1e-05", 1e-05),
            ("2.5e-07", 2.5e-07),
            ("-0.5", -0.5),
            (".5", 0.5),
            ("1.", 1.0),
            ("0.95", 0.95),
            ("1E5", 1e5),
            ("0.95 (use as input only)", 0.95),
            ("1e-05 (ok)", 1e-05),
        ):
            with self.subTest(text=text):
                self.assertEqual(kb_schema.number_token(text), expected)

    def test_no_number_is_none(self):
        for text in ("", "*pending*", "no digits here"):
            with self.subTest(text=text):
                self.assertIsNone(kb_schema.number_token(text))

    def test_every_finite_repr_round_trips(self):
        for number in (0.0, 1.0, 0.875, 0.0001, 1e-05, 2.5e-07, 4.0, 1e15, 1e16, 1.5e300, -1e-10, 5e-324):
            with self.subTest(number=number):
                self.assertEqual(kb_schema.number_token(repr(number)), number)


if __name__ == "__main__":
    unittest.main()
