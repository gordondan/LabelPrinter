import json
import os
import sys
from PIL import Image, ImageDraw, ImageFont


class LabelGenerator:
    def __init__(self, config):
        self.config = config
    
    def generate_label(self, text, printer_config, custom_settings=None):
        """Generate a label image with the given text
        
        Args:
            text: The text to put on the label
            printer_config: Printer-specific configuration
            custom_settings: Optional dict with custom label settings
        
        Returns:
            PIL.Image: The generated label image
        """
        # Merge custom settings if provided
        settings = {}
        if custom_settings:
            settings.update(custom_settings)
        
        # Create image based on printer-specific settings
        width_px = int(printer_config['label_width_in'] * printer_config['dpi'])
        height_px = int(printer_config['label_height_in'] * printer_config['dpi'])
        image = Image.new('L', (width_px, height_px), 255)
        draw = ImageDraw.Draw(image)
        
        # Get text height ratio (can be overridden)
        text_height_ratio = settings.get('text_height_ratio', 
                                       self.config.get('default_text_height_ratio', 0.15))
        
        # Calculate maximum dimensions
        max_text_height = int(height_px * text_height_ratio)
        max_text_width = int(width_px * self.config.get('max_text_width_ratio', 0.85))
        
        # Find the right font size
        min_font = self.config.get('min_font_size', 10)
        max_font = self.config.get('max_font_size', 500)
        font_size = min_font
        font_path = settings.get('font_path', self.config['font_path'])
        
        for size in range(min_font, max_font):
            # Test with 20% larger font size
            test_size = int(size * 1.2)
            test_size = min(test_size, max_font)
            
            font = ImageFont.truetype(font_path, test_size)
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            if text_height > max_text_height or text_width > max_text_width:
                font_size = size - 1
                break
            font_size = size
        
        # Apply 20% font size increase to the final optimal size
        font_size = int(font_size * 1.2)
        
        # Use the determined font size
        font = ImageFont.truetype(font_path, font_size)
        
        # Get text dimensions
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Calculate positioning
        x = (width_px - text_width) // 2
        
        # Vertical positioning
        bottom_margin = settings.get('bottom_margin', printer_config.get('bottom_margin', 15))
        y = height_px - bottom_margin - text_height
        
        # Calculate actual drawing position
        draw_x = x - bbox[0]
        draw_y = y - bbox[1]
        
        # Safety checks
        if draw_x < 0:
            print(f"WARNING: Text would be cut off on left! Adjusting from {draw_x} to 0")
            draw_x = 0
        
        right_edge = draw_x + text_width
        if right_edge > width_px:
            print(f"WARNING: Text would be cut off on right! Right edge: {right_edge}, limit: {width_px}")
            draw_x = width_px - text_width
        
        # Draw the text
        draw.text((draw_x, draw_y), text, font=font, fill=0)
        
        # Debug info if enabled
        if settings.get('debug', False):
            print(f"\n=== Label Generation Debug ===")
            print(f"Text: '{text}'")
            print(f"Font size: {font_size}, Text dimensions: {text_width}x{text_height}")
            print(f"Label dimensions: {width_px}x{height_px}")
            print(f"Draw position: ({draw_x}, {draw_y})")
            print(f"Bottom margin: {bottom_margin}px")
        
        return image