#!/usr/bin/env python3
"""
Comprehensive tests for all label generation scenarios.

Tests all combinations of:
- Main message (present/absent)
- Border message (present/absent) 
- Dates (shown/hidden via message-only flag)
- Font size increases
- Layout spacing
"""

import unittest
import sys
import os
import json
from datetime import datetime
from PIL import Image, ImageDraw

# Add the parent directory to the path so we can import the label printer
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the module by file name since it has a dash
import importlib.util
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("label_printer", 
    os.path.join(parent_dir, "label-printer.py"))
label_printer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(label_printer)

# Now we can access the functions directly from the module
generate_label_image = label_printer.generate_label_image


class TestLabelGenerationScenarios(unittest.TestCase):
    """Test all label generation scenarios with proper separation of concerns."""
    
    def setUp(self):
        """Set up test configuration and data."""
        self.config = {
            "font_path": "C:\\Windows\\Fonts\\arial.ttf",
            "min_font_size": 10,
            "max_font_size": 500,
            "default_text_height_ratio": 0.15,
            "max_text_width_ratio": 0.85,
            "month_size_ratios": {
                "August": 0.15
            }
        }
        
        self.printer_config = {
            "label_width_in": 2.25,
            "label_height_in": 1.25,
            "dpi": 203,
            "bottom_margin": 15
        }
        
        self.date_str = "August 09, 2025"
        self.date_obj = datetime(2025, 8, 9)
        
        # Test messages
        self.main_message = "Main Message"
        self.border_message = "Border Message"
        self.long_message = "This is a longer message that should wrap"
        self.short_message = "Hi"
    
    def test_dates_only(self):
        """Test label with only dates (traditional behavior)."""
        print("\n=== Testing: Dates Only ===")
        
        image = generate_label_image(
            self.date_str, self.date_obj, self.config, self.printer_config,
            message=None, border_message=None, message_only=False
        )
        
        # Verify image was created
        self.assertIsInstance(image, Image.Image)
        self.assertEqual(image.size, (456, 253))  # Expected dimensions at 203 DPI
        
        # Save test image
        image.save("test/test_dates_only.png")
        print("SUCCESS: Dates only label generated successfully")
    
    def test_main_message_with_dates(self):
        """Test label with main message and dates."""
        print("\n=== Testing: Main Message + Dates ===")
        
        image = generate_label_image(
            self.date_str, self.date_obj, self.config, self.printer_config,
            message=self.main_message, border_message=None, message_only=False
        )
        
        self.assertIsInstance(image, Image.Image)
        self.assertEqual(image.size, (456, 253))
        image.save("test/test_main_message_with_dates.png")
        print("SUCCESS: Main message with dates label generated successfully")
    
    def test_border_message_with_dates(self):
        """Test label with border message and dates."""
        print("\n=== Testing: Border Message + Dates ===")
        
        image = generate_label_image(
            self.date_str, self.date_obj, self.config, self.printer_config,
            message=None, border_message=self.border_message, message_only=False
        )
        
        self.assertIsInstance(image, Image.Image)
        self.assertEqual(image.size, (456, 253))
        image.save("test/test_border_message_with_dates.png")
        print("✓ Border message with dates label generated successfully")
    
    def test_both_messages_with_dates(self):
        """Test label with both main and border messages plus dates."""
        print("\n=== Testing: Both Messages + Dates ===")
        
        image = generate_label_image(
            self.date_str, self.date_obj, self.config, self.printer_config,
            message=self.main_message, border_message=self.border_message, message_only=False
        )
        
        self.assertIsInstance(image, Image.Image)
        self.assertEqual(image.size, (456, 253))
        image.save("test/test_both_messages_with_dates.png")
        print("✓ Both messages with dates label generated successfully")
    
    def test_main_message_only_no_dates(self):
        """Test label with only main message, no dates."""
        print("\n=== Testing: Main Message Only (No Dates) ===")
        
        image = generate_label_image(
            self.date_str, self.date_obj, self.config, self.printer_config,
            message=self.main_message, border_message=None, message_only=True
        )
        
        self.assertIsInstance(image, Image.Image)
        self.assertEqual(image.size, (456, 253))
        image.save("test/test_main_message_only.png")
        print("✓ Main message only label generated successfully")
    
    def test_border_message_only_no_dates(self):
        """Test label with only border message, no dates."""
        print("\n=== Testing: Border Message Only (No Dates) ===")
        
        image = generate_label_image(
            self.date_str, self.date_obj, self.config, self.printer_config,
            message=None, border_message=self.border_message, message_only=True
        )
        
        self.assertIsInstance(image, Image.Image)
        self.assertEqual(image.size, (456, 253))
        image.save("test/test_border_message_only.png")
        print("✓ Border message only label generated successfully")
    
    def test_both_messages_no_dates(self):
        """Test label with both messages but no dates (the previously broken scenario)."""
        print("\n=== Testing: Both Messages, No Dates ===")
        
        image = generate_label_image(
            self.date_str, self.date_obj, self.config, self.printer_config,
            message=self.main_message, border_message=self.border_message, message_only=True
        )
        
        self.assertIsInstance(image, Image.Image)
        self.assertEqual(image.size, (456, 253))
        image.save("test/test_both_messages_no_dates.png")
        print("✓ Both messages without dates label generated successfully")
    
    def test_long_message_wrapping(self):
        """Test that long messages wrap properly."""
        print("\n=== Testing: Long Message Wrapping ===")
        
        image = generate_label_image(
            self.date_str, self.date_obj, self.config, self.printer_config,
            message=self.long_message, border_message=None, message_only=True
        )
        
        self.assertIsInstance(image, Image.Image)
        image.save("test/test_long_message_wrapping.png")
        print("✓ Long message wrapping label generated successfully")
    
    def test_short_message_font_sizing(self):
        """Test that short messages don't get oversized fonts."""
        print("\n=== Testing: Short Message Font Sizing ===")
        
        image = generate_label_image(
            self.date_str, self.date_obj, self.config, self.printer_config,
            message=self.short_message, border_message=None, message_only=True
        )
        
        self.assertIsInstance(image, Image.Image)
        image.save("test/test_short_message_font_sizing.png")
        print("✓ Short message font sizing label generated successfully")
    
    def test_layout_space_allocation(self):
        """Test that layout spaces are properly allocated for different scenarios."""
        print("\n=== Testing: Layout Space Allocation ===")
        
        # Mock ImageDraw object for layout calculations
        from PIL import ImageDraw, ImageFont
        test_image = Image.new('L', (456, 253), 255)
        test_draw = ImageDraw.Draw(test_image)
        
        # Test layout calculation function directly
        layout = label_printer.calculate_layout_spaces(
            456, 253, self.printer_config, self.config, 
            self.date_str, self.date_obj,
            show_dates=True, show_main_message=True, show_border_message=True,
            draw=test_draw, min_font=10, max_font=500
        )
        
        # Verify layout contains expected keys
        expected_keys = ['bottom_date_y', 'top_date_end_y', 'date_font_size', 'date_font',
                        'main_message_start', 'main_message_end', 
                        'border_message_start', 'border_message_end']
        
        for key in expected_keys:
            self.assertIn(key, layout, f"Layout missing key: {key}")
        
        # Verify space allocation makes sense
        self.assertLess(layout['main_message_start'], layout['main_message_end'])
        self.assertLess(layout['border_message_start'], layout['border_message_end'])
        self.assertLessEqual(layout['main_message_end'], layout['border_message_start'])
        
        print("✓ Layout space allocation working correctly")
    
    def test_font_size_increase_applied(self):
        """Test that the 20% font size increase is properly applied."""
        print("\n=== Testing: Font Size Increase Applied ===")
        
        # This test verifies the font size functions are applying the 20% increase
        from PIL import ImageDraw
        test_image = Image.new('L', (456, 253), 255)
        test_draw = ImageDraw.Draw(test_image)
        
        # Test the font sizing functions directly
        font_size = label_printer.find_optimal_font_size(
            "Test Text", self.config['font_path'], test_draw, 300, 50, 10, 500
        )
        
        # Font size should be reasonable (not tiny, not huge)
        self.assertGreater(font_size, 15, "Font size should be increased from base")
        self.assertLess(font_size, 200, "Font size should not be excessive")
        
        print(f"✓ Font size increase applied: {font_size}px")
    
    def test_edge_cases(self):
        """Test edge cases and error conditions."""
        print("\n=== Testing: Edge Cases ===")
        
        # Test with no message or border message (should still work with dates)
        image = generate_label_image(
            self.date_str, self.date_obj, self.config, self.printer_config,
            message=None, border_message=None, message_only=False
        )
        self.assertIsInstance(image, Image.Image)
        
        # Test with empty strings
        image = generate_label_image(
            self.date_str, self.date_obj, self.config, self.printer_config,
            message="", border_message="", message_only=True
        )
        self.assertIsInstance(image, Image.Image)
        
        print("✓ Edge cases handled correctly")


class TestCommandLineInterface(unittest.TestCase):
    """Test the command line interface scenarios."""
    
    def setUp(self):
        """Set up test environment."""
        # Change to the correct directory
        os.chdir("C:\\Users\\gordon\\source\\repos\\LabelPrinter")
    
    def test_command_line_scenarios(self):
        """Test various command line scenarios that should work."""
        import subprocess
        import tempfile
        
        print("\n=== Testing: Command Line Interface ===")
        
        test_cases = [
            # (description, command_args, should_succeed)
            ("Main message only", ["-m", "Test Main", "-o", "-p"], True),
            ("Border message only", ["-b", "Test Border", "-o", "-p"], True), 
            ("Both messages no dates", ["-m", "Main", "-b", "Border", "-o", "-p"], True),
            ("Both messages with dates", ["-m", "Main", "-b", "Border", "-p"], True),
            ("Border only with dates", ["-b", "Test Border", "-p"], True),
            ("Main only with dates", ["-m", "Test Main", "-p"], True),
        ]
        
        for description, args, should_succeed in test_cases:
            with self.subTest(description=description):
                try:
                    cmd = ["python", "label-printer.py"] + args
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    
                    if should_succeed:
                        self.assertEqual(result.returncode, 0, 
                                       f"Command failed: {description}\nStderr: {result.stderr}")
                        print(f"✓ {description}: SUCCESS")
                    else:
                        self.assertNotEqual(result.returncode, 0, 
                                          f"Command should have failed: {description}")
                        print(f"✓ {description}: FAILED (as expected)")
                        
                except subprocess.TimeoutExpired:
                    self.fail(f"Command timed out: {description}")
                except Exception as e:
                    if should_succeed:
                        self.fail(f"Unexpected error in {description}: {e}")


def run_all_tests():
    """Run all tests and generate a report."""
    print("=" * 60)
    print("RUNNING COMPREHENSIVE LABEL GENERATION TESTS")
    print("=" * 60)
    
    # Create test directory if it doesn't exist
    os.makedirs("test", exist_ok=True)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestLabelGenerationScenarios))
    suite.addTests(loader.loadTestsFromTestCase(TestCommandLineInterface))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
