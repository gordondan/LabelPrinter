#!/usr/bin/env python3
"""
Visual analysis test to better understand the font sizing issue.
This creates multiple test labels with different approaches to verify proper sizing.
"""

import sys
import os
import importlib.util
from datetime import datetime

# Import the label-printer module
spec = importlib.util.spec_from_file_location("label_printer", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "label-printer.py"))
label_printer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(label_printer)

def create_test_configs():
    """Create test configuration."""
    test_config = {
        "font_path": "C:\\Windows\\Fonts\\arial.ttf",
        "date_format": "%B %d, %Y",
        "min_font_size": 10,
        "max_font_size": 500,
        "default_text_height_ratio": 0.15,
        "max_text_width_ratio": 0.85,
        "month_size_ratios": {"August": 0.15}
    }
    
    test_printer_config = {
        "label_width_in": 2.25,
        "label_height_in": 1.25,
        "dpi": 203,
        "bottom_margin": 15
    }
    
    return test_config, test_printer_config

def test_various_messages():
    """Test various message lengths to understand the pattern."""
    test_config, test_printer_config = create_test_configs()
    test_date = datetime(2025, 8, 9)
    date_str = test_date.strftime(test_config['date_format'])
    
    test_messages = [
        "A",           # 1 char
        "Hi",          # 2 chars  
        "Cat",         # 3 chars
        "Test",        # 4 chars
        "Hello",       # 5 chars
        "Chicken",     # 7 chars - the problematic one
        "Birthday",    # 8 chars
        "Important",   # 9 chars
        "This is long", # 12 chars
        "Very long message here"  # 22 chars
    ]
    
    print("MESSAGE LENGTH vs FONT SIZE ANALYSIS")
    print("=" * 60)
    print(f"{'Message':<25} {'Length':<8} {'Font Size':<10} {'Issue?':<6}")
    print("-" * 60)
    
    results = []
    
    for message in test_messages:
        # Generate label (suppress debug output)
        old_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
        try:
            image = label_printer.generate_label_image(
                date_str, test_date, test_config, test_printer_config, 
                message=message, message_only=True
            )
        finally:
            sys.stdout.close()
            sys.stdout = old_stdout
        
        # Extract font size by recreating the calculation
        width_px = int(test_printer_config['label_width_in'] * test_printer_config['dpi'])
        height_px = int(test_printer_config['label_height_in'] * test_printer_config['dpi'])
        
        # These are the values we observed from debug output
        space_start = 92
        space_end = 201 
        available_height = space_end - space_start
        max_message_width = int(width_px * 0.9)
        
        # Simulate the font sizing calculation
        from PIL import Image, ImageDraw
        test_img = Image.new('L', (width_px, height_px), 255)
        draw = ImageDraw.Draw(test_img)
        
        optimal_font_size, _, _ = label_printer.find_optimal_font_size_for_wrapped_text(
            message, test_config['font_path'], draw, 
            max_message_width, available_height, 10, 500
        )
        
        # Apply the reduction (same as in main code)  
        if optimal_font_size > 11:
            final_font_size = optimal_font_size - 2
        else:
            final_font_size = optimal_font_size
        
        # Determine if this is problematic (font too large for message length)
        max_reasonable = available_height // max(3, len(message) // 3)  # Scale by message length
        is_issue = final_font_size > max_reasonable
        
        print(f"{message:<25} {len(message):<8} {final_font_size:<10} {'YES' if is_issue else 'NO':<6}")
        results.append((message, len(message), final_font_size, is_issue))
    
    return results

def create_size_recommendation():
    """Create font size recommendations based on message length."""
    print("\n" + "=" * 60)
    print("FONT SIZE RECOMMENDATIONS")
    print("=" * 60)
    
    # Available space analysis
    space_height = 201 - 92  # 109 pixels
    max_width = int(456 * 0.9)  # 410 pixels
    
    print(f"Available space: {space_height} pixels high, {max_width} pixels wide")
    print(f"Current label size: 456x253 pixels (2.25\" x 1.25\" at 203 DPI)")
    
    recommendations = [
        ("Very short (1-2 chars)", "30-40", "Single letters shouldn't dominate"),
        ("Short (3-5 chars)", "25-35", "Leave room for readability"),
        ("Medium (6-10 chars)", "20-30", "Balanced size for common words"),
        ("Long (11-20 chars)", "15-25", "May need wrapping"),
        ("Very long (20+ chars)", "10-20", "Will definitely need wrapping")
    ]
    
    print("\nRecommended font size ranges:")
    for category, size_range, note in recommendations:
        print(f"  {category:<20}: {size_range:<8} pixels ({note})")
    
    print(f"\nCurrent issue: 'Chicken' (7 chars) is using ~140-145 pixel font")
    print(f"Recommended: 'Chicken' should use ~25-30 pixel font maximum")
    print(f"Problem: Font is 4-5x too large!")

def main():
    print("COMPREHENSIVE FONT SIZING ANALYSIS")
    print("=" * 60)
    print("This test analyzes the font sizing algorithm to understand")
    print("why short messages like 'Chicken' are getting oversized fonts.")
    print()
    
    # Test various message lengths
    results = test_various_messages()
    
    # Create recommendations
    create_size_recommendation()
    
    # Summary analysis
    print("\n" + "=" * 60)
    print("SUMMARY OF FINDINGS")
    print("=" * 60)
    
    issues = [r for r in results if r[3]]  # r[3] is the is_issue flag
    
    print(f"Messages tested: {len(results)}")
    print(f"Messages with oversized fonts: {len(issues)}")
    
    if issues:
        print(f"\nProblematic messages:")
        for msg, length, font_size, _ in issues:
            print(f"  '{msg}' ({length} chars): {font_size}px font")
    
    print(f"\nRoot cause: The font sizing algorithm doesn't consider message length")
    print(f"when determining maximum font size. Short messages get huge fonts")
    print(f"because they have lots of available space but don't need it all.")
    
    print(f"\nRecommendation: Modify the algorithm to:")
    print(f"1. Set maximum font size based on message characteristics")
    print(f"2. Use more conservative margin calculations") 
    print(f"3. Prevent font sizes that would make text dominate the label")

if __name__ == "__main__":
    main()