import time
import subprocess
import json
import os
import sys
import argparse
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

from logger import create_logger

# BLE printer module (no-op on Windows if you want)
try:
    from rw402b_ble.printer import RW402BPrinter
except Exception as e:
    # You can keep running in preview mode without this on Windows
    RW402BPrinter = None


# --- CONFIGURATION ---

import platform

def get_config_file():
    """Return the appropriate config file path based on OS."""
    system = platform.system().lower()
    if system == "windows":
        return "config/printer-config-windows.json"
    elif system == "linux":
        return "config/printer-config-linux.json"
    else:
        return "config/printer-config.json"

def load_config():
    """Load configuration from the appropriate JSON file based on OS."""
    config_file = get_config_file()
    if not os.path.exists(config_file):
        print(f"\nERROR: Configuration file '{config_file}' not found!")
        print("\nPlease create a printer-config.json file with the following structure:")
        print(json.dumps({
            "default_printer": "Your Printer Name",
            "date_format": "%B %d, %Y",
            "font_path": "C:\\Windows\\Fonts\\arial.ttf",
            "max_retries": 3,
            "wait_between_tries": 2,
            "pause_between_labels": 1,
            "month_size_ratios": {
                "January": 0.15,
                "February": 0.15
                # ... add other months as needed
            },
            "windows_device_caps": {
                "PHYSICALWIDTH": 110,
                "PHYSICALHEIGHT": 111,
                "LOGPIXELSX": 88,
                "LOGPIXELSY": 90,
                "HORZRES": 8,
                "VERTRES": 10,
                "PHYSICALOFFSETX": 112,
                "PHYSICALOFFSETY": 113
            },
            "printers": {
                "Your Printer Name": {
                    "label_width_in": 2.25,
                    "label_height_in": 1.25,
                    "dpi": 203,
                    "bottom_margin": 15,
                    "bluetooth_device_name": "",
                    "bluetooth_wait_time": 3
                }
            }
        }, indent=2))
        print("\nSee README.md for detailed configuration documentation.")
        sys.exit(1)

    # Load the config file
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        return config
    except json.JSONDecodeError as e:
        print(f"\nERROR: Invalid JSON in {config_file}: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: Failed to load {config_file}: {e}")
        sys.exit(1)

def save_config(config):
    """Save configuration to the appropriate JSON file based on OS."""
    config_file = get_config_file()
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

def get_printer_config(config, printer_name):
    """Get printer-specific configuration, creating default if needed"""
    if printer_name not in config.get("printers", {}):
        # Create default printer config
        if "printers" not in config:
            config["printers"] = {}
        config["printers"][printer_name] = {
            "label_width_in": 2.25,
            "label_height_in": 1.25,
            "dpi": 203,
            "bottom_margin": 15,
            "horizontal_offset": 0,
            "positioning_mode": "auto",
            "bluetooth_device_name": "",
            "bluetooth_wait_time": 3
        }
    return config["printers"][printer_name]



def wrap_text_to_fit(text, font, draw, max_width):
    """
    Wrap text at word boundaries to fit within max_width.
    Returns a list of lines.
    """
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        # Test if adding this word would exceed max width
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        test_width = bbox[2] - bbox[0]
        
        if test_width <= max_width:
            current_line.append(word)
        else:
            # If current line has words, finish it and start new line
            if current_line:
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                # Single word is too long, add it anyway to avoid infinite loop
                lines.append(word)
    
    # Add remaining words as final line
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines

def find_optimal_font_size(text, font_path, draw, max_width, max_height, min_size=10, max_size=500):
    """Find the largest font size that fits within the given constraints."""
    optimal_size = min_size
    for size in range(min_size, max_size):
        # Test with 20% larger font size
        test_size = int(size * 1.2)
        test_size = min(test_size, max_size)
        
        font = ImageFont.truetype(font_path, test_size)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        if text_height > max_height or text_width > max_width:
            optimal_size = max(size - 1, min_size)
            break
        optimal_size = size
    
    # Return the 20% increased size of the optimal base size
    return int(optimal_size * 1.2)

def find_optimal_font_size_for_wrapped_text(text, font_path, draw, max_width, max_height, min_size=10, max_size=500):
    """Find optimal font size for text that will be wrapped to fit within constraints."""
    optimal_size = int(min_size * 1.2)  # Initialize with 20% increased min size
    final_lines = []
    final_total_height = 0
    
    # Set a reasonable upper bound based on available height (don't let font be larger than 80% of available height)
    reasonable_max = min(max_size, int(max_height * 0.8))
    
    for size in range(min_size, reasonable_max):
        # Test with 20% larger font size
        test_size = int(size * 1.2)
        test_size = min(test_size, max_size)
        
        font = ImageFont.truetype(font_path, test_size)
        wrapped_lines = wrap_text_to_fit(text, font, draw, max_width)
        
        # Calculate total height needed for all lines
        line_heights = []
        for line in wrapped_lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_heights.append(bbox[3] - bbox[1])
        
        line_spacing = 2
        total_height = sum(line_heights) + (len(wrapped_lines) - 1) * line_spacing
        
        # Also check if text fits within width (important for single long words)
        text_width = 0
        for line in wrapped_lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
            text_width = max(text_width, line_width)
        
        if total_height <= max_height and text_width <= max_width:
            optimal_size = test_size  # Save the actual size we tested, not the base size
            final_lines = wrapped_lines
            final_total_height = total_height
            # Size accepted
            pass
        else:
            # Size rejected - break to avoid larger sizes
            break
    
    # Return the optimal size (already includes 20% increase)
    return optimal_size, final_lines, final_total_height

def draw_text_with_bold_effect(draw, position, text, font, fill=0):
    """Draw text with a bold effect by drawing multiple times with slight offsets."""
    x, y = position
    # Draw shadow/bold effect
    for offset_x in [-1, 0, 1]:
        for offset_y in [-1, 0, 1]:
            if offset_x == 0 and offset_y == 0:
                continue
            draw.text((x + offset_x, y + offset_y), text, font=font, fill=fill)
    
    # Draw main text
    draw.text((x, y), text, font=font, fill=fill)

def center_text_horizontally(text_width, container_width, bbox_left=0):
    """Calculate x position to center text horizontally."""
    logical_x = (container_width - text_width) // 2
    return logical_x - bbox_left

def draw_border(draw, width, height, margin=4, thickness=6):
    """Draw a border around the image."""
    left = margin
    top = margin
    right = width - margin
    bottom = height - margin
    
    for i in range(thickness):
        # Top border
        draw.rectangle([left + i, top + i, right - i, top + i], fill=0)
        # Bottom border
        draw.rectangle([left + i, bottom - i, right - i, bottom - i], fill=0)
        # Left border
        draw.rectangle([left + i, top + i, left + i, bottom - i], fill=0)
        # Right border
        draw.rectangle([right - i, top + i, right - i, bottom - i], fill=0)

def draw_date_at_bottom(draw, date_str, font, width_px, height_px, bottom_margin):
    """Draw date text at the bottom of the label."""
    bbox = draw.textbbox((0, 0), date_str, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Position and draw the date
    date_y = height_px - bottom_margin - text_height
    draw_x = center_text_horizontally(text_width, width_px, bbox[0])
    draw_y = date_y - bbox[1]
    
    # Safety bounds checking
    draw_x = max(0, min(draw_x, width_px - text_width))
    
    draw.text((draw_x, draw_y), date_str, font=font, fill=0)
    return date_y, text_height

def draw_rotated_date_at_top(image, draw, date_str, font, width_px, top_margin=15):
    """Draw rotated (upside down) date at the top of the label."""
    bbox = draw.textbbox((0, 0), date_str, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Create temporary image for rotation
    temp_img = Image.new('L', (text_width + 40, text_height + 40), 255)
    temp_draw = ImageDraw.Draw(temp_img)
    temp_draw.text((20 - bbox[0], 20 - bbox[1]), date_str, font=font, fill=0)
    
    # Rotate and position
    rotated_temp = temp_img.rotate(180, expand=True)
    rotated_x = (width_px - rotated_temp.width) // 2
    rotated_y = top_margin
    
    # Create mask and paste onto main image
    mask = rotated_temp.point(lambda x: 255 if x < 128 else 0, mode='1')
    black_overlay = Image.new('L', rotated_temp.size, 0)
    image.paste(black_overlay, (rotated_x, rotated_y), mask)
    
    return rotated_y + rotated_temp.height

def draw_rotated_text(image, draw, text, font, width_px, zone_start, zone_end, rotation=0):
    """Draw text in a zone with optional 180° rotation for bottom zones."""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    if rotation == 180:
        # Create temporary image for rotation (reusing existing rotation logic)
        temp_img = Image.new('L', (text_width + 40, text_height + 40), 255)
        temp_draw = ImageDraw.Draw(temp_img)
        temp_draw.text((20 - bbox[0], 20 - bbox[1]), text, font=font, fill=0)
        
        # Rotate 180 degrees
        rotated_temp = temp_img.rotate(180, expand=True)
        
        # Calculate position in zone
        zone_center_y = (zone_start + zone_end) // 2
        rotated_x = (width_px - rotated_temp.width) // 2
        rotated_y = zone_center_y - rotated_temp.height // 2
        
        # Create mask and paste onto main image
        mask = rotated_temp.point(lambda x: 255 if x < 128 else 0, mode='1')
        black_overlay = Image.new('L', rotated_temp.size, 0)
        image.paste(black_overlay, (rotated_x, rotated_y), mask)
        
    else:
        # Normal orientation - center in zone
        zone_center_y = (zone_start + zone_end) // 2
        draw_x = center_text_horizontally(text_width, width_px, bbox[0])
        draw_y = zone_center_y - text_height // 2 - bbox[1]
        draw.text((draw_x, draw_y), text, font=font, fill=0)

def draw_text_in_zone(image, draw, text, font_path, zone_start, zone_end, width_px, rotation=0, min_font=10, max_font=500, extra_padding=0, layout=None):
    """DRY function to draw text in any zone with proper font sizing and optional rotation."""
    # Apply additional padding if specified (for border text)
    effective_zone_start = zone_start + extra_padding
    effective_zone_end = zone_end - extra_padding
    available_height = effective_zone_end - effective_zone_start
    
    # Use printable width if layout is provided, otherwise fallback to 90% of total width
    if layout and 'printable_width' in layout:
        max_text_width = int(layout['printable_width'] * 0.95)  # 95% of printable width for safety
    else:
        max_text_width = int(width_px * 0.9)
    
    font_size, wrapped_lines, total_height = find_optimal_font_size_for_wrapped_text(
        text, font_path, draw, max_text_width, available_height, min_font, max_font
    )
    
    # Removed debug output for cleaner production use
    
    font = ImageFont.truetype(font_path, font_size)
    
    if len(wrapped_lines) == 1:
        # Single line - use rotation-aware drawing with effective zones
        draw_rotated_text(image, draw, wrapped_lines[0], font, width_px, effective_zone_start, effective_zone_end, rotation)
    else:
        # Multiple lines - use centered message approach (no rotation for wrapped text)
        if rotation == 0:
            draw_centered_message(draw, text, font_path, width_px, effective_zone_start, effective_zone_end, min_font, max_font)
        else:
            # For rotated multi-line text, fall back to single line or handle differently
            draw_rotated_text(image, draw, text, font, width_px, effective_zone_start, effective_zone_end, rotation)

def draw_centered_message(draw, message, font_path, width_px, space_start, space_end, min_font=10, max_font=500):
    """Draw a centered message with text wrapping and bold effect."""
    available_height = space_end - space_start
    max_message_width = int(width_px * 0.9)
    
    # Find optimal font size and get wrapped lines
    message_font_size, final_lines, final_total_height = find_optimal_font_size_for_wrapped_text(
        message, font_path, draw, max_message_width, available_height, min_font, max_font
    )
    
    if not final_lines:  # Fallback if no size works
        font = ImageFont.truetype(font_path, min_font)
        final_lines = wrap_text_to_fit(message, font, draw, max_message_width)
        final_total_height = len(final_lines) * min_font  # Rough estimate
        message_font_size = min_font
    
    message_font = ImageFont.truetype(font_path, message_font_size)
    
    # Calculate vertical centering
    block_start_y = space_start + (available_height - final_total_height) // 2
    
    # Draw each line centered
    current_y = block_start_y
    line_spacing = 2
    
    for line in final_lines:
        bbox = draw.textbbox((0, 0), line, font=message_font)
        text_width = bbox[2] - bbox[0]
        
        draw_x = center_text_horizontally(text_width, width_px, bbox[0])
        draw_y = current_y - bbox[1]
        
        # Draw with bold effect
        draw_text_with_bold_effect(draw, (draw_x, draw_y), line, message_font)
        
        current_y += (bbox[3] - bbox[1]) + line_spacing
    
    return message_font_size, final_lines, block_start_y

def calculate_layout_spaces(width_px, height_px, printer_config, config, date_str, date_obj, 
                           show_dates, show_main_message, show_border_message, show_side_border, draw, min_font, max_font):
    """
    Calculate layout spaces using proper zone-based layout:
    - Top Zone (25%): Border text (readable right-side-up)
    - Middle Zone (50%): Main message or dates
    - Bottom Zone (25%): Border text (readable right-side-up, mirrored)
    - 3px padding throughout
    """
    layout = {}
    
    # Calculate printable area inside the border (4px margin + 6px thickness = 10px from edges)
    border_margin = 4
    border_thickness = 6
    border_offset = border_margin + border_thickness
    
    printable_width = width_px - (2 * border_offset)
    printable_height = height_px - (2 * border_offset)
    printable_start_y = border_offset
    
    # Define the 25%/50%/25% zones within printable area with 3px padding
    padding = 3
    zone_height = printable_height / 4  # Each 25% zone of printable area
    
    # Top zone (25% of printable area) - for border text
    layout['top_zone_start'] = printable_start_y + padding
    layout['top_zone_end'] = printable_start_y + int(zone_height) - padding
    
    # Middle zone (50% of printable area) - for main content
    layout['middle_zone_start'] = printable_start_y + int(zone_height) + padding
    layout['middle_zone_end'] = printable_start_y + int(3 * zone_height) - padding
    
    # Bottom zone (25% of printable area) - for border text (mirrored)
    layout['bottom_zone_start'] = printable_start_y + int(3 * zone_height) + padding
    layout['bottom_zone_end'] = printable_start_y + printable_height - padding
    
    # Calculate side border zones if needed
    if show_side_border:
        # Side borders span from bottom of top border to top of bottom border with 6px padding
        side_border_padding = 6
        layout['left_side_start_y'] = layout['top_zone_end'] + side_border_padding  
        layout['left_side_end_y'] = layout['bottom_zone_start'] - side_border_padding
        layout['right_side_start_y'] = layout['left_side_start_y']
        layout['right_side_end_y'] = layout['left_side_end_y']
        
        # Side borders are narrow zones on left and right
        side_border_width = int(zone_height)  # Use same width as top/bottom border height
        layout['left_side_start_x'] = border_offset + padding
        layout['left_side_end_x'] = layout['left_side_start_x'] + side_border_width
        layout['right_side_start_x'] = border_offset + printable_width - side_border_width - padding  
        layout['right_side_end_x'] = border_offset + printable_width - padding
    
    # Adjust printable width if side borders are present
    effective_printable_width = printable_width
    effective_printable_start_x = border_offset
    
    if show_side_border:
        # Reduce printable width by side border width on both sides
        side_border_width = int(zone_height)  # Same width as calculated above
        effective_printable_width = printable_width - (2 * side_border_width) - (2 * padding)
        effective_printable_start_x = border_offset + side_border_width + padding
    
    # Store effective printable dimensions for width validation
    layout['printable_width'] = effective_printable_width
    layout['printable_height'] = printable_height
    layout['printable_start_x'] = effective_printable_start_x
    layout['printable_start_y'] = printable_start_y
    
    # Determine what goes in each zone based on content type
    if show_border_message and not show_main_message and not show_dates:
        # Border message only: goes in top and bottom zones
        layout['border_top_start'] = layout['top_zone_start']
        layout['border_top_end'] = layout['top_zone_end']
        layout['border_bottom_start'] = layout['bottom_zone_start']
        layout['border_bottom_end'] = layout['bottom_zone_end']
        
    elif show_main_message and not show_border_message and not show_dates:
        # Main message only: goes in middle zone
        layout['main_message_start'] = layout['middle_zone_start']
        layout['main_message_end'] = layout['middle_zone_end']
        
    elif show_dates and not show_main_message and not show_border_message:
        # Dates only: goes in middle zone
        layout['date_start'] = layout['middle_zone_start']
        layout['date_end'] = layout['middle_zone_end']
        
    elif show_main_message and show_border_message and not show_dates:
        # Both messages, no dates: main in middle, border in top/bottom
        layout['main_message_start'] = layout['middle_zone_start']
        layout['main_message_end'] = layout['middle_zone_end']
        layout['border_top_start'] = layout['top_zone_start']
        layout['border_top_end'] = layout['top_zone_end']
        layout['border_bottom_start'] = layout['bottom_zone_start']
        layout['border_bottom_end'] = layout['bottom_zone_end']
        
    elif show_dates and show_main_message and not show_border_message:
        # Dates + main message: dates in top/bottom, main in middle
        layout['main_message_start'] = layout['middle_zone_start']
        layout['main_message_end'] = layout['middle_zone_end']
        layout['date_top_start'] = layout['top_zone_start']
        layout['date_top_end'] = layout['top_zone_end']
        layout['date_bottom_start'] = layout['bottom_zone_start']
        layout['date_bottom_end'] = layout['bottom_zone_end']
        
    elif show_dates and show_border_message and not show_main_message:
        # Dates + border message: dates in middle, border in top/bottom
        layout['date_start'] = layout['middle_zone_start']
        layout['date_end'] = layout['middle_zone_end']
        layout['border_top_start'] = layout['top_zone_start']
        layout['border_top_end'] = layout['top_zone_end']
        layout['border_bottom_start'] = layout['bottom_zone_start']
        layout['border_bottom_end'] = layout['bottom_zone_end']
        
    elif show_dates and show_main_message and show_border_message:
        # All three: dates in top/bottom, main in middle, border overlaid or split
        # This is a complex case - for now, prioritize dates and main message
        layout['main_message_start'] = layout['middle_zone_start']
        layout['main_message_end'] = layout['middle_zone_end']
        layout['date_top_start'] = layout['top_zone_start']
        layout['date_top_end'] = layout['top_zone_end']
        layout['date_bottom_start'] = layout['bottom_zone_start']
        layout['date_bottom_end'] = layout['bottom_zone_end']
    
    # Calculate font information for dates if needed
    if show_dates:
        month_name = date_obj.strftime("%B")
        base_ratio = 0.8  # Use most of the zone height
        max_date_height = int((layout.get('date_top_end', layout.get('date_end', zone_height)) - 
                              layout.get('date_top_start', layout.get('date_start', 0))) * base_ratio)
        max_text_width = int(width_px * 0.9)  # 90% of width
        
        date_font_size = find_optimal_font_size(date_str, config['font_path'], draw, max_text_width, max_date_height, min_font, max_font)
        layout['date_font_size'] = date_font_size
        layout['date_font'] = ImageFont.truetype(config['font_path'], date_font_size)
    
    return layout

def draw_dates(image, draw, date_str, config, layout, skip_rotated_date):
    """Draw dates in their allocated zones with proper rotation."""
    # Draw date in middle zone
    if 'date_start' in layout:
        draw_centered_message(draw, date_str, config['font_path'], image.width, 
                            layout['date_start'], layout['date_end'], 10, 500)
    
    # Draw dates in top and bottom zones with rotation
    if 'date_top_start' in layout and 'date_bottom_start' in layout:
        # Top zone - normal orientation
        draw_text_in_zone(image, draw, date_str, config['font_path'],
                         layout['date_top_start'], layout['date_top_end'],
                         image.width, rotation=0, min_font=10, max_font=500)
        
        # Bottom zone - 180° rotation for readability from opposite side  
        draw_text_in_zone(image, draw, date_str, config['font_path'],
                         layout['date_bottom_start'], layout['date_bottom_end'],
                         image.width, rotation=180, min_font=10, max_font=500)

def draw_main_message(image, draw, message, config, layout, width_px):
    """Draw main message in the middle zone with proper size validation."""
    if 'main_message_start' in layout:
        space_start = layout['main_message_start']
        space_end = layout['main_message_end']
        
        # Use the new zone-based function with layout info for width validation
        draw_text_in_zone(image, draw, message, config['font_path'],
                         space_start, space_end, width_px, 
                         rotation=0, min_font=10, max_font=500, extra_padding=0, layout=layout)

def load_and_process_image(image_path, printable_width, printable_height, logger):
    """Load PNG image and crop to fit printable area if necessary."""
    try:
        # Load the image
        user_image = Image.open(image_path)
        
        # Convert to grayscale to match label format
        if user_image.mode != 'L':
            user_image = user_image.convert('L')
            logger.log(f"Converted image from {Image.open(image_path).mode} to grayscale")
        
        original_width, original_height = user_image.size
        logger.log(f"Loaded image: {original_width}x{original_height}px from {image_path}")
        
        # Check if image needs cropping
        if original_width > printable_width or original_height > printable_height:
            # Crop from top-left corner to fit printable area
            cropped_image = user_image.crop((0, 0, min(original_width, printable_width), 
                                           min(original_height, printable_height)))
            
            # Log warning about cropping
            logger.log(f"WARNING: Image {original_width}x{original_height}px is larger than printable area {printable_width}x{printable_height}px")
            logger.log(f"Image cropped to {cropped_image.size[0]}x{cropped_image.size[1]}px from top-left corner")
            print(f"WARNING: Image cropped from {original_width}x{original_height}px to {cropped_image.size[0]}x{cropped_image.size[1]}px")
            
            return cropped_image
        else:
            logger.log(f"Image fits within printable area - no cropping needed")
            return user_image
            
    except FileNotFoundError:
        logger.log(f"ERROR: Image file not found: {image_path}")
        print(f"ERROR: Image file not found: {image_path}")
        return None
    except Exception as e:
        logger.log(f"ERROR: Failed to load image {image_path}: {str(e)}")
        print(f"ERROR: Failed to load image: {str(e)}")
        return None

def paste_image_on_label(base_image, user_image, layout):
    """Paste user image onto label in the appropriate location."""
    if user_image is None:
        return
    
    # Calculate position to center the image in the printable area
    printable_start_x = layout.get('printable_start_x', 10)
    printable_start_y = layout.get('printable_start_y', 10)
    printable_width = layout.get('printable_width', base_image.width - 20)
    printable_height = layout.get('printable_height', base_image.height - 20)
    
    image_width, image_height = user_image.size
    
    # Center the image in the printable area
    paste_x = printable_start_x + (printable_width - image_width) // 2
    paste_y = printable_start_y + (printable_height - image_height) // 2
    
    # Paste the image onto the base label
    base_image.paste(user_image, (paste_x, paste_y))

def draw_side_border_message(image, draw, side_border, config, layout, width_px, height_px):
    """Draw side border message on left and right with 90°/-90° rotation."""
    if 'left_side_start_x' not in layout:
        return
    
    # Calculate font size for side text (use same height as top/bottom borders)
    available_height = layout['left_side_end_y'] - layout['left_side_start_y']
    available_width = layout['left_side_end_x'] - layout['left_side_start_x']
    
    # Find optimal font size for the text in the side area
    # Since text will be rotated, we swap width/height for font calculation
    font_size, wrapped_lines, total_height = find_optimal_font_size_for_wrapped_text(
        side_border, config['font_path'], draw, available_height, available_width - 8, 10, 500
    )
    
    font = ImageFont.truetype(config['font_path'], font_size)
    
    # Draw left side (90° clockwise rotation)
    # For side borders, join wrapped lines with spaces to keep text on one "line"
    text = ' '.join(wrapped_lines)
    
    # Create temporary image for left side text (90° rotation)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    temp_img = Image.new('L', (text_width + 20, text_height + 20), 255)
    temp_draw = ImageDraw.Draw(temp_img)
    temp_draw.text((10 - bbox[0], 10 - bbox[1]), text, font=font, fill=0)
    
    # Rotate 90° clockwise for left side
    rotated_left = temp_img.rotate(-90, expand=True)
    
    # Position on left side
    left_center_x = (layout['left_side_start_x'] + layout['left_side_end_x']) // 2
    left_center_y = (layout['left_side_start_y'] + layout['left_side_end_y']) // 2
    paste_x = left_center_x - rotated_left.width // 2
    paste_y = left_center_y - rotated_left.height // 2
    
    # Paste left side text
    mask = rotated_left.point(lambda x: 255 if x < 128 else 0, mode='1')
    black_overlay = Image.new('L', rotated_left.size, 0)
    image.paste(black_overlay, (paste_x, paste_y), mask)
    
    # Draw right side (90° counter-clockwise rotation)
    rotated_right = temp_img.rotate(90, expand=True)
    
    # Position on right side  
    right_center_x = (layout['right_side_start_x'] + layout['right_side_end_x']) // 2
    right_center_y = (layout['right_side_start_y'] + layout['right_side_end_y']) // 2
    paste_x = right_center_x - rotated_right.width // 2
    paste_y = right_center_y - rotated_right.height // 2
    
    # Paste right side text
    mask = rotated_right.point(lambda x: 255 if x < 128 else 0, mode='1')
    black_overlay = Image.new('L', rotated_right.size, 0)
    image.paste(black_overlay, (paste_x, paste_y), mask)

def draw_border_message(image, draw, border_message, config, layout, width_px):
    """Draw border message in top and bottom zones with proper 180° rotation for bottom."""
    # Calculate optimal padding for border text (~4px for good balance)
    # Maintains visual spacing while maximizing readable font size
    border_padding = 4
    
    # Draw in top zone (normal orientation) with extra padding
    if 'border_top_start' in layout:
        draw_text_in_zone(image, draw, border_message, config['font_path'], 
                         layout['border_top_start'], layout['border_top_end'], 
                         width_px, rotation=0, min_font=10, max_font=500, extra_padding=border_padding, layout=layout)
    
    # Draw in bottom zone (180° rotation for readability from opposite side) with extra padding
    if 'border_bottom_start' in layout:
        draw_text_in_zone(image, draw, border_message, config['font_path'],
                         layout['border_bottom_start'], layout['border_bottom_end'],
                         width_px, rotation=180, min_font=10, max_font=500, extra_padding=border_padding, layout=layout)

def reconnect_bluetooth_device(device_name):
    """
    On Raspberry Pi, BLE connection is handled automatically by the BLE routines in rw402b_ble/printer.py.
    No manual reconnect is needed; a new connection will be attempted each print.
    """
    
def generate_label_image(date_str, date_obj, config, printer_config, message=None, border_message=None, side_border=None, show_date=False, image_path=None, logger=None):
    """Generate a label image with dates and/or message."""
    # Create image based on printer-specific settings
    width_px = int(printer_config['label_width_in'] * printer_config['dpi'])
    height_px = int(printer_config['label_height_in'] * printer_config['dpi'])
    image = Image.new('L', (width_px, height_px), 255)
    draw = ImageDraw.Draw(image)

    # Get font configuration
    min_font = config.get('min_font_size', 10)
    max_font = config.get('max_font_size', 500)
    
    # Determine what content to show
    show_dates = show_date  # Now dates are only shown when -o flag is present
    show_main_message = message is not None
    show_border_message = border_message is not None
    show_side_border = side_border is not None
    
    # Calculate layout spaces based on what content we're showing
    layout = calculate_layout_spaces(width_px, height_px, printer_config, config, date_str, date_obj, 
                                    show_dates, show_main_message, show_border_message, show_side_border, draw, min_font, max_font)
    
    # Layout calculation complete
    
    # Load and process user image if provided
    user_image = None
    if image_path:
        printable_width = layout.get('printable_width', width_px - 20)
        printable_height = layout.get('printable_height', height_px - 20)
        user_image = load_and_process_image(image_path, printable_width, printable_height, logger)
        
        # Paste the image onto the label (behind text content)
        if user_image:
            paste_image_on_label(image, user_image, layout)
    
    # Draw each type of content in its allocated space (over the image)
    if show_dates:
        draw_dates(image, draw, date_str, config, layout, show_border_message)
    
    if show_main_message:
        draw_main_message(image, draw, message, config, layout, width_px)
    
    if show_border_message:
        draw_border_message(image, draw, border_message, config, layout, width_px)
    
    if show_side_border:
        draw_side_border_message(image, draw, side_border, config, layout, width_px, height_px)
    
    # Draw border
    draw_border(draw, width_px, height_px)
    
    # Debug output
    print(f"\n=== Debug Info ===")
    print(f"Show dates: {show_dates}")
    if show_dates:
        print(f"Date string: '{date_str}', font size: {layout.get('date_font_size', 'N/A')}")
    if show_main_message:
        print(f"Message: '{message}' (length: {len(message)})")
    if show_border_message:
        print(f"Border message: '{border_message}' (length: {len(border_message)})")
    if show_side_border:
        print(f"Side border message: '{side_border}' (length: {len(side_border)})")
    print(f"Label dimensions: {width_px}x{height_px}")
    
    image.save("label_preview.png")  # Optional preview
    return image

def print_label(image, printer_name, config, printer_config):
    """
    On Linux/Pi: send the PIL image to RW402B over BLE using TSPL.
    """

    # ---- Linux/Pi BLE path ----
    if RW402BPrinter is None:
        print("BLE printer module not available. Install it or run in --preview-only.")
        return False

    try:
        dpi = int(printer_config.get('dpi', 203))
        label_w_in = float(printer_config.get('label_width_in', 2.25))
        label_h_in = float(printer_config.get('label_height_in', 1.25))

        # Convert inches -> mm for TSPL SIZE command
        label_w_mm = label_w_in * 25.4
        label_h_mm = label_h_in * 25.4

        gap_mm     = float(printer_config.get('gap_mm', 3.0))
        density    = int(printer_config.get('density', 8))
        speed      = int(printer_config.get('speed', 4))
        direction  = int(printer_config.get('direction', 1))
        invert     = bool(printer_config.get('invert', True))  # you found invert=True works

        # Optional: fixed BLE MAC; if absent we auto-scan by name (RW402B/Munbyn/Beeprt)
        ble_mac = printer_config.get('ble_mac') or None

        # Fire!
        p = RW402BPrinter(addr=ble_mac, timeout=float(printer_config.get('bluetooth_wait_time', 4.0)),
                          dpi=dpi, invert=invert)
        p.print_pil_image(
            image,
            label_w_mm=label_w_mm,
            label_h_mm=label_h_mm,
            gap_mm=gap_mm,
            density=density,
            speed=speed,
            direction=direction,
            x=0, y=0, mode=0
        )
        print("Label sent over BLE to RW402B.")
        return True

    except Exception as e:
        print(f"BLE printing failed: {e}")
        import traceback
        traceback.print_exc()
        return False



def _print_profiling_summary(profile):
    """Print a concise profiling summary of major steps."""
    def ms(sec):
        return int(sec * 1000)

    print("\n=== Profiling Summary ===")
    if 'config_load' in profile:
        print(f"Config load: {ms(profile.get('config_load', 0))} ms")
    if 'bluetooth_wait' in profile and profile.get('bluetooth_wait', 0) > 0:
        print(f"Bluetooth wait: {ms(profile.get('bluetooth_wait', 0))} ms")
    if 'image_generation' in profile:
        print(f"Image generation: {ms(profile.get('image_generation', 0))} ms")
    if 'preview_save' in profile:
        print(f"Preview save: {ms(profile.get('preview_save', 0))} ms")

    # Printing details
    prints = profile.get('print_success_times', [])
    attempts = profile.get('print_attempt_times', [])
    if attempts:
        total_attempt_time = sum(attempts)
        print(f"Print attempts: {len(attempts)} attempts, {ms(total_attempt_time)} ms total")
    if prints:
        total_print_time = sum(prints)
        avg = total_print_time / len(prints)
        print(f"Successful prints: {len(prints)}, total {ms(total_print_time)} ms, avg {ms(avg)} ms")
    elif attempts:
        print("Successful prints: 0")

    # Total wall time
    if 'start' in profile and 'end' in profile:
        total = profile['end'] - profile['start']
        print(f"Total runtime: {ms(total)} ms")


if __name__ == "__main__":
    _profile = {
        'start': time.perf_counter(),
        'print_success_times': [],
        'print_attempt_times': [],
    }
    # Initialize logger
    logger = create_logger()
    
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description='Print date labels on a thermal label printer',
        epilog='Configuration is stored in printer-config.json (must be created manually)'
    )
    parser.add_argument('-c', '--count', type=int, default=1, 
                        help='Number of labels to print (default: 1)')
    parser.add_argument('-d', '--date', type=str, 
                        help='Specific date to print (format: YYYY-MM-DD, default: today)')
    parser.add_argument('-m', '--message', type=str, 
                        help='Custom message to print in center of label')
    parser.add_argument('-b', '--border-message', type=str,
                        help='Custom border message - appears on top and bottom borders with rotation')
    parser.add_argument('-s', '--side-border', type=str,
                        help='Custom side border message - appears on left and right sides with 90°/-90° rotation')
    parser.add_argument('-i', '--image', type=str,
                        help='Path to PNG image file to include on label (will be cropped to fit printable area if oversized)')
    parser.add_argument('-o', '--show-date', action='store_true',
                        help='Show dates on the label (dates are hidden by default)')
    parser.add_argument('-p', '--preview-only', action='store_true',
                        help='Generate label image only (do not print to printer)')
    args = parser.parse_args()
    
    # Log the command execution
    logger.log_command("label-printer.py", sys.argv[1:])
    
    # Load configuration
    _t0 = time.perf_counter()
    config = load_config()
    _profile['config_load'] = time.perf_counter() - _t0
    logger.log("Configuration loaded successfully")
    
    # Step 1: Get printer selection
    selected_printer = "RW402B"
    
    # Get printer-specific configuration
    printer_config = get_printer_config(config, selected_printer)
    
    # Step 2: Try to connect to Bluetooth printer (best effort)
    if printer_config['bluetooth_device_name']:
        _t0 = time.perf_counter()
        reconnect_bluetooth_device(printer_config['bluetooth_device_name'])
        print("Waiting for Bluetooth device to connect...")
        time.sleep(printer_config['bluetooth_wait_time'])
        _profile['bluetooth_wait'] = time.perf_counter() - _t0

    # Step 3: Generate the label image
    if args.date:
        try:
            # Parse the provided date
            date_obj = datetime.strptime(args.date, "%Y-%m-%d")
            date_str = date_obj.strftime(config['date_format'])
            print(f"Using specified date: {date_str}")
        except ValueError:
            print(f"Invalid date format: {args.date}. Please use YYYY-MM-DD format.")
            exit(1)
    else:
        date_obj = datetime.now()
        date_str = date_obj.strftime(config['date_format'])
    
    # Log label generation details
    logger.log_label_generation(date_str, args.message, args.border_message, not args.show_date, args.count)
    
    _t0 = time.perf_counter()
    label_img = generate_label_image(date_str, date_obj, config, printer_config, args.message, args.border_message, args.side_border, args.show_date, args.image, logger)
    _profile['image_generation'] = time.perf_counter() - _t0
    print(f"Label image generated for: {date_str}")
    logger.log_success("Label image generated", f"Date: {date_str}, Dimensions: {label_img.size}")
    
    # Save preview to log directory
    _t0 = time.perf_counter()
    logger.save_label_preview(label_img)
    _profile['preview_save'] = time.perf_counter() - _t0

    # Step 4: Print the requested number of labels (or just generate preview)
    if args.preview_only:
        print(f"Preview mode: Label image generated only (not printed)")
        logger.log("Preview mode: No printing requested")
    else:
        print(f"\nPrinting {args.count} label(s)...")
        logger.log(f"Starting print job: {args.count} label(s) to {selected_printer}")
    
        for label_num in range(1, args.count + 1):
            if args.count > 1:
                print(f"\nLabel {label_num} of {args.count}:")
                logger.log(f"Printing label {label_num} of {args.count}")
            
            # Try printing with retries
            for attempt in range(config['max_retries']):
                print(f"  Print attempt {attempt + 1} of {config['max_retries']}...")
                logger.log(f"Print attempt {attempt + 1} of {config['max_retries']}")
                _t0 = time.perf_counter()
                success = print_label(label_img, selected_printer, config, printer_config)
                _elapsed = time.perf_counter() - _t0
                _profile['print_attempt_times'].append(_elapsed)
                if success:
                    _profile['print_success_times'].append(_elapsed)
                    logger.log_success(f"Label {label_num} printed successfully")
                    if label_num < args.count:
                        time.sleep(config.get('pause_between_labels', 1))
                    break
                else:
                    logger.log_error(f"Print attempt {attempt + 1} failed")
                    print(f"  Retrying in {config['wait_between_tries']} seconds...")
                    time.sleep(config['wait_between_tries'])
            else:
                error_msg = "Failed to print after multiple attempts. Is the printer powered on, paired, and connected?"
                print(error_msg)
                logger.log_error(error_msg)
                _profile['end'] = time.perf_counter()
                _print_profiling_summary(_profile)
                exit(1)
    
        print(f"\nSuccessfully printed {args.count} label(s).")
        logger.log_success("Print job completed", f"{args.count} label(s) printed successfully")

    # Always print profiling summary at the end
    _profile['end'] = time.perf_counter()
    _print_profiling_summary(_profile)
