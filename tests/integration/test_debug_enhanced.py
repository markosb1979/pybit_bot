#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import sys
import os
import inspect

class TestDebugEnhanced(unittest.TestCase):
    def setUp(self):
        print("\nSetting up test")
        
    def test_debug_test_discovery(self):
        """Enhanced debug test to diagnose test discovery issues."""
        print("Running enhanced debug test")
        
        # Check test files in integration directory
        integration_dir = os.path.dirname(os.path.abspath(__file__))
        print(f"Integration test directory: {integration_dir}")
        
        test_files = [f for f in os.listdir(integration_dir) if f.startswith('test_') and f.endswith('.py')]
        print(f"Test files found: {test_files}")
        
        # Check for test classes and methods in this directory
        for file in test_files:
            module_name = f"tests.integration.{file[:-3]}"
            try:
                module = __import__(module_name, fromlist=['*'])
                
                # Find test classes
                test_classes = [obj for name, obj in inspect.getmembers(module) 
                               if inspect.isclass(obj) and issubclass(obj, unittest.TestCase)]
                
                print(f"\nFile: {file}")
                print(f"Test classes found: {[cls.__name__ for cls in test_classes]}")
                
                # Find test methods in each class
                for cls in test_classes:
                    test_methods = [name for name, _ in inspect.getmembers(cls) 
                                   if name.startswith('test_')]
                    print(f"  Class {cls.__name__} has methods: {test_methods}")
                    
            except ImportError as e:
                print(f"Error importing {module_name}: {str(e)}")
                
        self.assertTrue(True)

if __name__ == "__main__":
    unittest.main(verbosity=2)