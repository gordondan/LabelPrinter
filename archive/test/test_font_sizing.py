#!/usr/bin/env python3
"""
Test suite for label printer font sizing validation.
Tests various string lengths and ensures proper margins are maintained.
"""

import sys
import os
import json
import tempfile
import unittest
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# Add the parent directory to the path to import the main module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import importlib.util
import importlib

# Import the label-printer module
spec = importlib.util.spec_from_file_location("label_printer", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "label-printer.py"))
label_printer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(label_printer)

generate_label_image = label_printer.generate_label_image
find_optimal_font_size = label_printer.find_optimal_font_size
find_optimal_font_size_for_wrapped_text = label_printer.find_optimal_font_size_for_wrapped_text
wrap_text_to_fit = label_printer.wrap_text_to_fit

class TestFontSizing(unittest.TestCase):
    """Test cases for font sizing functionality."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test configuration and printer settings."""
        cls.test_config = {
            "font_path": "C:\\Windows\\Fonts\\arial.ttf",
            "date_format": "%B %d, %Y",
            "min_font_size": 10,
            "max_font_size": 500,
            "default_text_height_ratio": 0.15,
            "max_text_width_ratio": 0.85,
            "month_size_ratios": {
                "January": 0.15,
                "February": 0.15,
                "March": 0.15,
                "April": 0.15,
                "May": 0.15,
                "June": 0.15,
                "July": 0.15,
                "August": 0.15,
                "September": 0.15,
                "October": 0.15,
                "November": 0.15,
                "December": 0.15
            }
        }
        
        cls.test_printer_config = {
            "label_width_in": 2.25,
            "label_height_in": 1.25,
            "dpi": 203,
            "bottom_margin": 15
        }
        
        # Calculate label dimensions
        cls.width_px = int(cls.test_printer_config['label_width_in'] * cls.test_printer_config['dpi'])
        cls.height_px = int(cls.test_printer_config['label_height_in'] * cls.test_printer_config['dpi'])
        
        # Define margin thresholds for testing
        cls.SAFE_MARGIN_TOP = 20    # Minimum top margin for readability
        cls.SAFE_MARGIN_BOTTOM = 20 # Minimum bottom margin for readability  
        cls.SAFE_MARGIN_LEFT = 15   # Minimum left margin for readability
        cls.SAFE_MARGIN_RIGHT = 15  # Minimum right margin for readability
    
    def setUp(self):
        """Set up each test."""
        self.test_date = datetime(2025, 8, 9)
        self.date_str = self.test_date.strftime(self.test_config['date_format'])
        
    def test_short_message_sizing(self):
        """Test that short messages don't get oversized."""
        test_cases = [
            "Hi",
            "OK", 
            "Yes",
            "Cat",
            "Dog",
            "Go"
        ]
        
        for message in test_cases:
            with self.subTest(message=message):
                # Generate label with message only
                image = generate_label_image(
                    self.date_str, self.test_date, self.test_config, 
                    self.test_printer_config, message=message, message_only=True
                )
                
                # Verify the text fits properly with safe margins
                self.assertTrue(self._verify_text_margins(image, message))
                
                # Verify font isn't excessively large for short text
                font_size = self._extract_font_size_from_debug_output(message)
                max_reasonable_font = min(100, self.height_px // 3)  # No more than 1/3 of height
                self.assertLessEqual(font_size, max_reasonable_font,
                    f"Font size {font_size} too large for short message '{message}'")

    def test_medium_message_sizing(self):
        """Test medium-length messages."""
        test_cases = [
            "Chicken",
            "Kitchen", 
            "Meeting",
            "Birthday",
            "Appointment",
            "Important"
        ]
        
        for message in test_cases:
            with self.subTest(message=message):
                image = generate_label_image(
                    self.date_str, self.test_date, self.test_config, 
                    self.test_printer_config, message=message, message_only=True
                )
                
                self.assertTrue(self._verify_text_margins(image, message))
                
                # Medium text should be reasonably sized
                font_size = self._extract_font_size_from_debug_output(message)
                self.assertGreaterEqual(font_size, 20, f"Font too small for '{message}'")
                self.assertLessEqual(font_size, 80, f"Font too large for '{message}'")

    def test_long_message_sizing(self):
        """Test long messages that should wrap or scale down."""
        test_cases = [
            "This is a longer message",
            "Please remember to clean up after yourself",
            "Meeting scheduled for next week",
            "Don't forget your appointment tomorrow morning",
            "Very long message that should definitely wrap to multiple lines"
        ]
        
        for message in test_cases:
            with self.subTest(message=message):
                image = generate_label_image(
                    self.date_str, self.test_date, self.test_config, 
                    self.test_printer_config, message=message, message_only=True
                )
                
                self.assertTrue(self._verify_text_margins(image, message))
                
                # Long text should use smaller fonts
                font_size = self._extract_font_size_from_debug_output(message)
                self.assertGreaterEqual(font_size, 10, f"Font too small for '{message}'")
                self.assertLessEqual(font_size, 50, f"Font too large for long message '{message}'")

    def test_very_long_message_sizing(self):
        """Test very long messages."""
        test_cases = [
            "This is an extremely long message that should really be broken down into multiple lines and use very small fonts to fit properly within the label boundaries",
            "A" * 100,  # 100 characters
            "Word " * 20  # 20 words
        ]
        
        for message in test_cases:
            with self.subTest(message=message):
                image = generate_label_image(
                    self.date_str, self.test_date, self.test_config, 
                    self.test_printer_config, message=message, message_only=True
                )
                
                self.assertTrue(self._verify_text_margins(image, message))
                
                # Very long text should use minimum or near-minimum fonts
                font_size = self._extract_font_size_from_debug_output(message)
                self.assertGreaterEqual(font_size, 10, f"Font too small for '{message}'")
                self.assertLessEqual(font_size, 25, f"Font too large for very long message")

    def test_message_with_dates_preserves_space(self):
        """Test that when both message and dates are shown, proper space is preserved."""
        test_messages = ["Chicken", "Birthday Party", "Meeting at 3pm"]
        
        for message in test_messages:
            with self.subTest(message=message):
                # Generate with both dates and message
                image = generate_label_image(
                    self.date_str, self.test_date, self.test_config, 
                    self.test_printer_config, message=message, message_only=False
                )
                
                # Verify margins are preserved
                self.assertTrue(self._verify_text_margins(image, message))
                
                # Verify dates are visible (dates should be at top and bottom)
                self.assertTrue(self._verify_dates_are_visible(image))

    def test_font_scaling_algorithm(self):
        """Test the font scaling algorithms directly."""
        # Create a test drawing context
        test_image = Image.new('L', (self.width_px, self.height_px), 255)
        draw = ImageDraw.Draw(test_image)
        
        # Test single-line font sizing
        test_text = "Test"
        max_width = self.width_px - 2 * self.SAFE_MARGIN_LEFT
        max_height = 50
        
        font_size = find_optimal_font_size(
            test_text, self.test_config['font_path'], draw, 
            max_width, max_height, 10, 500
        )
        
        # Verify the font actually fits
        font = ImageFont.truetype(self.test_config['font_path'], font_size)
        bbox = draw.textbbox((0, 0), test_text, font=font)
        actual_width = bbox[2] - bbox[0]
        actual_height = bbox[3] - bbox[1]
        
        self.assertLessEqual(actual_width, max_width, "Font width exceeds constraint")
        self.assertLessEqual(actual_height, max_height, "Font height exceeds constraint")

    def test_text_wrapping(self):
        """Test text wrapping functionality."""
        test_image = Image.new('L', (self.width_px, self.height_px), 255)
        draw = ImageDraw.Draw(test_image)
        
        font = ImageFont.truetype(self.test_config['font_path'], 30)
        max_width = self.width_px - 2 * self.SAFE_MARGIN_LEFT
        
        test_cases = [
            "This is a long message that should wrap",
            "Short",
            "One Two Three Four Five Six Seven Eight Nine Ten"
        ]
        
        for text in test_cases:
            with self.subTest(text=text):
                lines = wrap_text_to_fit(text, font, draw, max_width)
                
                # Verify each line fits within width
                for line in lines:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    line_width = bbox[2] - bbox[0]
                    self.assertLessEqual(line_width, max_width, 
                        f"Wrapped line '{line}' exceeds max width")

    def test_optimal_wrapped_font_sizing(self):
        """Test font sizing for wrapped text."""
        test_image = Image.new('L', (self.width_px, self.height_px), 255)
        draw = ImageDraw.Draw(test_image)
        
        max_width = self.width_px - 2 * self.SAFE_MARGIN_LEFT
        max_height = self.height_px - 2 * self.SAFE_MARGIN_TOP
        
        test_text = "This is a moderately long message that might need wrapping"
        
        font_size, lines, total_height = find_optimal_font_size_for_wrapped_text(
            test_text, self.test_config['font_path'], draw, 
            max_width, max_height, 10, 500
        )
        
        # Verify the result fits within constraints
        self.assertLessEqual(total_height, max_height, "Total text height exceeds constraint")
        self.assertGreater(len(lines), 0, "No lines generated")
        
        # Verify each line fits within width
        font = ImageFont.truetype(self.test_config['font_path'], font_size)
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
            self.assertLessEqual(line_width, max_width, f"Line '{line}' too wide")

    def test_margin_preservation_stress_test(self):
        """Stress test to ensure margins are always preserved."""
        stress_test_cases = [
            "A",
            "AB", 
            "ABC",
            "ABCD",
            "ABCDE",
            "ABCDEF",
            "ABCDEFG",
            "ABCDEFGH",
            "ABCDEFGHI",
            "ABCDEFGHIJ",
            "This is getting longer",
            "Now this is really getting much longer",
            "This message is intentionally very long to test the margin preservation under extreme conditions",
            "WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW"  # Wide characters
        ]
        
        for message in stress_test_cases:
            with self.subTest(message=message[:20] + "..."):  # Limit output for readability
                image = generate_label_image(
                    self.date_str, self.test_date, self.test_config, 
                    self.test_printer_config, message=message, message_only=True
                )
                
                # This is the critical test - margins must ALWAYS be preserved
                self.assertTrue(self._verify_text_margins(image, message),
                    f"Margins violated for message: {message[:50]}...")

    def _verify_text_margins(self, image, message):
        """
        Verify that text respects safe margins by checking for black pixels
        in the margin areas.
        """
        width, height = image.size
        pixels = image.load()
        
        # Check top margin
        for y in range(self.SAFE_MARGIN_TOP):
            for x in range(width):
                if pixels[x, y] < 128:  # Black pixel found
                    print(f"Top margin violation at ({x}, {y}) for message: '{message}'")
                    return False
        
        # Check bottom margin
        for y in range(height - self.SAFE_MARGIN_BOTTOM, height):
            for x in range(width):
                if pixels[x, y] < 128:  # Black pixel found
                    print(f"Bottom margin violation at ({x}, {y}) for message: '{message}'")
                    return False
        
        # Check left margin
        for x in range(self.SAFE_MARGIN_LEFT):
            for y in range(height):
                if pixels[x, y] < 128:  # Black pixel found (ignoring border)
                    # Allow border pixels (first few pixels)
                    if x > 6:  # Border is 6 pixels thick
                        print(f"Left margin violation at ({x}, {y}) for message: '{message}'")
                        return False
        
        # Check right margin  
        for x in range(width - self.SAFE_MARGIN_RIGHT, width):
            for y in range(height):
                if pixels[x, y] < 128:  # Black pixel found
                    # Allow border pixels
                    if x < width - 6:  # Border is 6 pixels thick
                        print(f"Right margin violation at ({x}, {y}) for message: '{message}'")
                        return False
        
        return True
    
    def _verify_dates_are_visible(self, image):
        """Check that dates are visible in top and bottom areas."""
        width, height = image.size
        pixels = image.load()
        
        # Check for text in top area (excluding border)
        top_text_found = False
        for y in range(10, 60):  # Top area where rotated date should be
            for x in range(10, width - 10):
                if pixels[x, y] < 128:  # Found black pixel (text)
                    top_text_found = True
                    break
            if top_text_found:
                break
        
        # Check for text in bottom area (excluding border)
        bottom_text_found = False  
        for y in range(height - 60, height - 10):  # Bottom area where date should be
            for x in range(10, width - 10):
                if pixels[x, y] < 128:  # Found black pixel (text)
                    bottom_text_found = True
                    break
            if bottom_text_found:
                break
        
        return top_text_found and bottom_text_found
    
    def _extract_font_size_from_debug_output(self, message):
        """
        Extract font size from debug output. Since we can't easily capture
        stdout in this context, we'll re-run the font sizing algorithm.
        """
        test_image = Image.new('L', (self.width_px, self.height_px), 255)
        draw = ImageDraw.Draw(test_image)
        
        # Simulate the same calculation as in generate_label_image
        available_height = self.height_px - 94 - (self.height_px - 199)  # Rough calculation
        max_message_width = int(self.width_px * 0.9)
        
        optimal_font_size, _, _ = find_optimal_font_size_for_wrapped_text(
            message, self.test_config['font_path'], draw, 
            max_message_width, available_height, 10, 500
        )
        
        # Apply the same reduction as in the main code
        if optimal_font_size > 11:
            final_font_size = optimal_font_size - 2
        else:
            final_font_size = optimal_font_size
            
        return final_font_size


def run_font_sizing_tests():
    """Run all font sizing tests and generate a report."""
    print("Running Font Sizing Tests...")
    print("=" * 50)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestFontSizing)
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 50)
    print("FONT SIZING TEST SUMMARY")
    print("=" * 50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print(f"\nFAILURES:")
        for test, failure in result.failures:
            print(f"  - {test}: {failure.split('AssertionError:')[-1].strip()}")
    
    if result.errors:
        print(f"\nERRORS:")
        for test, error in result.errors:
            print(f"  - {test}: {error.split('Exception:')[-1].strip()}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_font_sizing_tests()
    sys.exit(0 if success else 1)