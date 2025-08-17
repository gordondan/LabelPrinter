#!/usr/bin/env python3
"""
Font Size Validation Test Suite
This test validates that font sizing works correctly for various string lengths
and ensures top/bottom areas are preserved for messages/dates.

Usage: python test/test_font_size_validation.py

This test should PASS after font sizing algorithm improvements are implemented.
Currently it will FAIL, demonstrating the issues that need to be fixed.
"""

import sys
import os
import importlib.util
from datetime import datetime

# Import the label-printer module
spec = importlib.util.spec_from_file_location("label_printer", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "label-printer.py"))
label_printer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(label_printer)

class FontSizeValidator:
    """Validates font sizing for label printer."""
    
    def __init__(self):
        self.config = {
            "font_path": "C:\\Windows\\Fonts\\arial.ttf",
            "date_format": "%B %d, %Y",
            "min_font_size": 10,
            "max_font_size": 500,
            "default_text_height_ratio": 0.15,
            "max_text_width_ratio": 0.85,
            "month_size_ratios": {"August": 0.15}
        }
        
        self.printer_config = {
            "label_width_in": 2.25,
            "label_height_in": 1.25,
            "dpi": 203,
            "bottom_margin": 15
        }
        
        self.test_date = datetime(2025, 8, 9)
        self.date_str = self.test_date.strftime(self.config['date_format'])
        
        # Define acceptable font size ranges based on message characteristics
        self.FONT_SIZE_LIMITS = {
            'very_short': (10, 40),   # 1-2 characters
            'short': (10, 35),        # 3-5 characters  
            'medium': (10, 30),       # 6-10 characters
            'long': (10, 25),         # 11-20 characters
            'very_long': (10, 20)     # 20+ characters
        }
    
    def get_category(self, message):
        """Categorize message by length."""
        length = len(message)
        if length <= 2:
            return 'very_short'
        elif length <= 5:
            return 'short'
        elif length <= 10:
            return 'medium'
        elif length <= 20:
            return 'long'
        else:
            return 'very_long'
    
    def get_font_size(self, message):
        """Extract font size for a given message."""
        # Suppress debug output
        old_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
        try:
            label_printer.generate_label_image(
                self.date_str, self.test_date, self.config, self.printer_config,
                message=message, message_only=True
            )
        finally:
            sys.stdout.close() 
            sys.stdout = old_stdout
        
        # Calculate font size using same logic as label printer
        width_px = int(self.printer_config['label_width_in'] * self.printer_config['dpi'])
        height_px = int(self.printer_config['label_height_in'] * self.printer_config['dpi'])
        
        from PIL import Image, ImageDraw
        test_img = Image.new('L', (width_px, height_px), 255)
        draw = ImageDraw.Draw(test_img)
        
        # Use same space calculations as main code
        space_start = 92
        space_end = 201
        available_height = space_end - space_start
        max_message_width = int(width_px * 0.9)
        
        optimal_font_size, _, _ = label_printer.find_optimal_font_size_for_wrapped_text(
            message, self.config['font_path'], draw,
            max_message_width, available_height, 10, 500
        )
        
        # Apply same reduction as main code
        if optimal_font_size > 11:
            final_font_size = optimal_font_size - 2
        else:
            final_font_size = optimal_font_size
            
        return final_font_size
    
    def validate_font_size(self, message):
        """Validate that font size is appropriate for message."""
        font_size = self.get_font_size(message)
        category = self.get_category(message)
        min_size, max_size = self.FONT_SIZE_LIMITS[category]
        
        return {
            'message': message,
            'length': len(message),
            'category': category,
            'font_size': font_size,
            'min_allowed': min_size,
            'max_allowed': max_size,
            'is_valid': min_size <= font_size <= max_size,
            'issue': None if min_size <= font_size <= max_size else 
                    f"Font {font_size}px outside range {min_size}-{max_size}px"
        }
    
    def run_validation_tests(self):
        """Run comprehensive validation tests."""
        test_messages = [
            # Very short messages (should use small-medium fonts)
            "A", "Hi", "OK", "Go",
            
            # Short messages (should use reasonable fonts)
            "Cat", "Dog", "Yes", "Test", "Hello",
            
            # Medium messages (the problematic "Chicken" case)
            "Chicken", "Kitchen", "Meeting", "Birthday", "Important",
            
            # Long messages (should use smaller fonts) 
            "This is long", "Meeting at 3pm", "Don't forget", "Remember this",
            
            # Very long messages (should use smallest fonts)
            "This is a very long message", "Please remember to clean up after yourself",
            "This message is intentionally very long to test the system"
        ]
        
        results = []
        for message in test_messages:
            result = self.validate_font_size(message)
            results.append(result)
        
        return results
    
    def print_results(self, results):
        """Print validation results in a readable format."""
        print("FONT SIZE VALIDATION RESULTS")
        print("=" * 80)
        print(f"{'Message':<30} {'Len':<4} {'Cat.':<10} {'Font':<5} {'Range':<10} {'Valid':<6} {'Issue'}")
        print("-" * 80)
        
        valid_count = 0
        for result in results:
            message = result['message'][:27] + "..." if len(result['message']) > 30 else result['message']
            status = "PASS" if result['is_valid'] else "FAIL"
            issue = result['issue'] if result['issue'] else ""
            range_str = f"{result['min_allowed']}-{result['max_allowed']}"
            
            print(f"{message:<30} {result['length']:<4} {result['category']:<10} "
                  f"{result['font_size']:<5} {range_str:<10} {status:<6} {issue}")
            
            if result['is_valid']:
                valid_count += 1
        
        print("\n" + "=" * 80)
        print(f"SUMMARY: {valid_count}/{len(results)} tests passed ({valid_count/len(results)*100:.1f}%)")
        
        if valid_count == len(results):
            print("SUCCESS: All font sizes are within acceptable ranges!")
        else:
            print("ISSUES FOUND: Font sizing algorithm needs improvement.")
            
        return valid_count == len(results)

def main():
    """Main test execution."""
    print("Label Printer Font Size Validation")
    print("This test validates font sizing for various message lengths.")
    print("It ensures fonts are appropriately sized and don't dominate labels.")
    print()
    
    validator = FontSizeValidator()
    results = validator.run_validation_tests()
    success = validator.print_results(results)
    
    print("\nTEST EXPECTATIONS:")
    print("- Very short messages (1-2 chars) should use 10-40px fonts")
    print("- Short messages (3-5 chars) should use 10-35px fonts") 
    print("- Medium messages (6-10 chars) should use 10-30px fonts")
    print("- Long messages (11-20 chars) should use 10-25px fonts")
    print("- Very long messages (20+ chars) should use 10-20px fonts")
    print()
    print("The 'Chicken' issue: 7-character word should use ~20-30px font,")
    print("not the current ~140px font that bleeds over margins.")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)