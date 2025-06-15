#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest

class TestBasic(unittest.TestCase):
    def test_simple(self):
        """A simple test to verify test discovery."""
        print("Running basic test")
        self.assertEqual(1, 1)
        
    def test_with_assert(self):
        """Test with an assertion."""
        x = 1 + 1
        print(f"1 + 1 = {x}")
        self.assertEqual(x, 2)

if __name__ == "__main__":
    unittest.main(verbosity=2)