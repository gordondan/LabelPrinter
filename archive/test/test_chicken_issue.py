#!/usr/bin/env python3
"""
Simple test for the specific "Chicken" label issue.
This test validates that the "Chicken" text doesn't bleed over margins.
"""

import sys
import os
import importlib.util
from datetime import datetime

# Import the label-printer module
spec = importlib.util.spec_from_file_location("label_printer", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "label-printer.py"))
label_printer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(label_printer)

def test_chicken_label():
    """Test the specific 'Chicken' label issue reported by user."""
    print("Testing 'Chicken' label font sizing...")
    
    # Set up test configuration
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
    
    test_date = datetime(2025, 8, 9)
    date_str = test_date.strftime(test_config['date_format'])
    message = "Chicken"
    
    # Generate the label
    image = label_printer.generate_label_image(
        date_str, test_date, test_config, test_printer_config, 
        message=message, message_only=True
    )
    
    # Analyze the image
    width, height = image.size
    pixels = image.load()
    
    print(f"Label dimensions: {width}x{height}")
    print(f"Message: '{message}'")
    
    # Check for text bleeding - look for black pixels near edges
    SAFE_MARGIN = 10  # Pixels from edge (excluding border)
    BORDER_THICKNESS = 6  # Border is 6 pixels thick
    
    # Check all 4 margins for text bleeding
    issues = []
    
    # Top margin (exclude border area)
    for y in range(BORDER_THICKNESS, SAFE_MARGIN + BORDER_THICKNESS):
        for x in range(BORDER_THICKNESS, width - BORDER_THICKNESS):
            if pixels[x, y] < 128:  # Black pixel (text)
                issues.append(f"Text found in top margin at ({x}, {y})")
                break
        if issues:
            break
    
    # Bottom margin (exclude border area)  
    for y in range(height - SAFE_MARGIN - BORDER_THICKNESS, height - BORDER_THICKNESS):
        for x in range(BORDER_THICKNESS, width - BORDER_THICKNESS):
            if pixels[x, y] < 128:  # Black pixel (text)
                issues.append(f"Text found in bottom margin at ({x}, {y})")
                break
        if issues and len(issues) == 1:  # Don't double-report
            break
    
    # Left margin (exclude border area)
    for x in range(BORDER_THICKNESS, SAFE_MARGIN + BORDER_THICKNESS):
        for y in range(BORDER_THICKNESS, height - BORDER_THICKNESS):
            if pixels[x, y] < 128:  # Black pixel (text)
                issues.append(f"Text found in left margin at ({x}, {y})")
                break
        if len([i for i in issues if "left margin" in i]) > 0:
            break
    
    # Right margin (exclude border area)
    for x in range(width - SAFE_MARGIN - BORDER_THICKNESS, width - BORDER_THICKNESS):
        for y in range(BORDER_THICKNESS, height - BORDER_THICKNESS):
            if pixels[x, y] < 128:  # Black pixel (text)
                issues.append(f"Text found in right margin at ({x}, {y})")
                break
        if len([i for i in issues if "right margin" in i]) > 0:
            break
    
    # Report results
    if issues:
        print("X MARGIN VIOLATIONS DETECTED:")
        for issue in issues:
            print(f"  - {issue}")
        print(f"\nThe 'Chicken' text is bleeding into the margins!")
        print("This confirms the user's reported issue.")
        return False
    else:
        print("OK No margin violations detected.")
        print("The 'Chicken' text fits properly within safe margins.")
        return True

def analyze_font_size():
    """Analyze what font size is being used for 'Chicken'."""
    print("\nAnalyzing font size calculation...")
    
    # Simulate the same calculation from generate_label_image
    width_px = int(2.25 * 203)  # 456
    height_px = int(1.25 * 203)  # 253
    
    print(f"Label size: {width_px}x{height_px}")
    
    # These values come from the debug output we saw earlier
    space_start = 92
    space_end = 201
    available_height = space_end - space_start
    max_message_width = int(width_px * 0.9)
    
    print(f"Available space: {space_start} to {space_end} = {available_height} pixels high")
    print(f"Max width: {max_message_width} pixels")
    
    # The current font size from our test was 140 (reduced by 2 from 142)
    current_font_size = 140
    print(f"Current font size: {current_font_size}")
    
    # Calculate what a more reasonable font size would be
    # A good rule of thumb: font should not exceed 1/3 of available height for short text
    max_reasonable_font = available_height // 3
    print(f"Recommended maximum font size: {max_reasonable_font}")
    
    if current_font_size > max_reasonable_font:
        print(f"X Current font ({current_font_size}) is {current_font_size - max_reasonable_font} pixels too large!")
        return max_reasonable_font
    else:
        print("OK Font size is within reasonable limits")
        return current_font_size

if __name__ == "__main__":
    print("=" * 60)
    print("CHICKEN LABEL FONT SIZE TEST")
    print("=" * 60)
    
    # Test for margin violations
    margins_ok = test_chicken_label()
    
    # Analyze font sizing
    recommended_size = analyze_font_size()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    if margins_ok:
        print("OK No margin violations detected")
    else:
        print("X Margin violations found - font is too large")
    
    print(f"Recommended action: Reduce maximum font size to ~{recommended_size} for short messages")
    print("\nThis test validates the user's report that 'Chicken' text is too large.")