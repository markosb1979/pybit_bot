#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import sys
import os

class TestDebug(unittest.TestCase):
    def setUp(self):
        print("\nSetting up test")
        
    def test_debug(self):
        """Debug test to verify test discovery in integration tests."""
        print("Running debug test")
        print(f"Python path: {sys.path}")
        print(f"Current directory: {os.getcwd()}")
        self.assertTrue(True)

if __name__ == "__main__":
    unittest.main(verbosity=2)