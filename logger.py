#!/usr/bin/env python3
"""
Logging module for label printer applications.
Creates timestamped log directories and handles log file management.
"""

import os
import shutil
from datetime import datetime
from pathlib import Path


class LabelPrinterLogger:
    """Logger for label printer operations."""
    
    def __init__(self, base_dir="logs", auto_create=True):
        """
        Initialize the logger.
        
        Args:
            base_dir: Base directory for logs (default: "logs")
            auto_create: Automatically create log directory structure
        """
        self.base_dir = Path(base_dir)
        self.current_log_dir = None
        self.log_file_path = None
        
        if auto_create:
            self.create_log_session()
    
    def create_log_session(self):
        """Create a new log session with timestamped directory."""
        now = datetime.now()
        year = now.strftime('%Y')
        month = now.strftime('%B')
        day = now.strftime('%B %d')
        time_str = now.strftime('%I-%M-%S %p')  # "03-30-45 PM"
        
        self.current_log_dir = self.base_dir / year / month / day / "runs" / time_str
        self.current_log_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_file_path = self.current_log_dir / "log.txt"
        
        # Write initial log entry
        self.log(f"=== Label Printer Log Session Started ===")
        self.log(f"Timestamp: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        self.log(f"Log directory: {self.current_log_dir}")
        self.log("")
        
        return self.current_log_dir
    
    def log(self, message):
        """
        Write a message to the log file.
        
        Args:
            message: Message to log
        """
        if not self.log_file_path:
            self.create_log_session()
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        
        try:
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(log_entry + '\n')
                f.flush()  # Ensure immediate write
        except Exception as e:
            print(f"Warning: Could not write to log file: {e}")
    
    def log_command(self, command, args=None):
        """
        Log a command execution.
        
        Args:
            command: Command name
            args: Command arguments (optional)
        """
        if args:
            self.log(f"Command: {command} {' '.join(str(arg) for arg in args)}")
        else:
            self.log(f"Command: {command}")
    
    def log_label_generation(self, date_str, message=None, border_message=None, message_only=False, count=1):
        """
        Log label generation details.
        
        Args:
            date_str: Date string used
            message: Main message (optional)
            border_message: Border message (optional) 
            message_only: Whether in message-only mode
            count: Number of labels
        """
        self.log("--- Label Generation ---")
        self.log(f"Date: {date_str}")
        if message:
            self.log(f"Message: '{message}' (length: {len(message)})")
        if border_message:
            self.log(f"Border message: '{border_message}' (length: {len(border_message)})")
        self.log(f"Message-only mode: {message_only}")
        self.log(f"Label count: {count}")
    
    def log_font_info(self, text, font_size, lines, text_type="message"):
        """
        Log font sizing information.
        
        Args:
            text: Text that was sized
            font_size: Final font size used
            lines: Lines of text after wrapping
            text_type: Type of text (message, border_message, date)
        """
        self.log(f"{text_type.title()} font: '{text}' -> {font_size}px")
        if len(lines) > 1:
            self.log(f"  Wrapped into {len(lines)} lines: {lines}")
    
    def log_printer_info(self, printer_name, label_dimensions, printer_info=None):
        """
        Log printer information.
        
        Args:
            printer_name: Name of printer
            label_dimensions: (width, height) in pixels
            printer_info: Additional printer details (optional)
        """
        self.log("--- Printer Information ---")
        self.log(f"Printer: {printer_name}")
        self.log(f"Label dimensions: {label_dimensions[0]}x{label_dimensions[1]} pixels")
        if printer_info:
            for key, value in printer_info.items():
                self.log(f"  {key}: {value}")
    
    def log_error(self, error_msg, exception=None):
        """
        Log an error.
        
        Args:
            error_msg: Error message
            exception: Exception object (optional)
        """
        self.log(f"ERROR: {error_msg}")
        if exception:
            self.log(f"  Exception: {str(exception)}")
    
    def log_success(self, operation, details=None):
        """
        Log a successful operation.
        
        Args:
            operation: Operation that succeeded
            details: Additional details (optional)
        """
        self.log(f"SUCCESS: {operation}")
        if details:
            self.log(f"  Details: {details}")
    
    def save_label_preview(self, image, filename="label_preview.png"):
        """
        Save label preview image to log directory.
        
        Args:
            image: PIL Image object
            filename: Filename for preview
        """
        if not self.current_log_dir:
            self.create_log_session()
        
        preview_path = self.current_log_dir / filename
        try:
            image.save(preview_path)
            self.log(f"Preview saved: {preview_path}")
            # Also mirror into recent using the same folder structure under logs
            try:
                # Compute the relative session subpath under the base logs directory
                rel = self.current_log_dir.relative_to(self.base_dir)
                archive_root = self.base_dir.parent / "recent"
                archive_dir = archive_root / rel
                archive_dir.mkdir(parents=True, exist_ok=True)
                archive_path = archive_dir / filename
                image.save(archive_path)
                self.log(f"Preview archived: {archive_path}")
            except Exception as e:
                self.log(f"WARNING: Could not mirror preview to recent: {e}")
            return preview_path
        except Exception as e:
            self.log_error(f"Could not save preview to {preview_path}", e)
            return None
    
    def get_log_directory(self):
        """Get the current log directory path."""
        return self.current_log_dir
    
    def get_log_file_path(self):
        """Get the current log file path."""
        return self.log_file_path
    
    def mirror_request_file(self, filename="request.json"):
        """Mirror a request.json file from logs to recent."""
        try:
            source_path = self.current_log_dir / filename
            if not source_path.is_file():
                return
                
            # Compute the relative session subpath under the base logs directory
            rel = self.current_log_dir.relative_to(self.base_dir)
            archive_root = self.base_dir.parent / "recent"
            archive_dir = archive_root / rel
            archive_dir.mkdir(parents=True, exist_ok=True)
            archive_path = archive_dir / filename
            
            # Copy the request file
            import shutil
            shutil.copy2(source_path, archive_path)
            self.log(f"Request file mirrored: {archive_path}")
        except Exception as e:
            self.log(f"WARNING: Could not mirror request file to recent: {e}")


def create_logger(base_dir="logs"):
    """
    Convenience function to create a logger instance.
    
    Args:
        base_dir: Base directory for logs
        
    Returns:
        LabelPrinterLogger instance
    """
    return LabelPrinterLogger(base_dir)


# Example usage
if __name__ == "__main__":
    # Test the logger
    logger = create_logger()
    
    logger.log("Testing the logger module")
    logger.log_command("test_command", ["arg1", "arg2"])
    logger.log_label_generation("August 09, 2025", "Test Message", count=1)
    logger.log_font_info("Test Message", 45, ["Test Message"])
    logger.log_printer_info("Test Printer", (456, 253))
    logger.log_success("Logger test completed")
    
    print(f"Log created at: {logger.get_log_file_path()}")