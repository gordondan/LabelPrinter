#!/usr/bin/env python3
"""
Label Printer Web Server
Enhanced Flask server that provides both API endpoints and a modern web interface
for the label printer functionality.
"""

import os
import sys
import json
import socket
import subprocess
from datetime import datetime
from pathlib import Path
import importlib.util

from flask import Flask, Response, request, jsonify, send_from_directory, render_template_string
from werkzeug.middleware.proxy_fix import ProxyFix

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import label printer functionality
try:
    from logger import create_logger
    # Import the label-printer module
    spec = importlib.util.spec_from_file_location("label_printer", 
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "label-printer.py"))
    label_printer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(label_printer)
except ImportError as e:
    print(f"Warning: Could not import label printer modules: {e}")
    label_printer = None

# Initialize Flask app
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Initialize logger
logger = create_logger("logs/server")

def get_local_ip():
    """Get the local IP address of the machine."""
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        if s:
            s.close()
    return ip

def load_config():
    """Load printer configuration."""
    try:
        config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "printer-config.json")
        with open(config_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.log_error(f"Could not load configuration: {e}")
        return None

def get_templates():
    """Get available label templates."""
    templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "label-images")
    templates = {}
    
    if os.path.exists(templates_dir):
        for category in os.listdir(templates_dir):
            category_path = os.path.join(templates_dir, category)
            if os.path.isdir(category_path):
                templates[category] = []
                for file in os.listdir(category_path):
                    if file.endswith('.template'):
                        template_path = os.path.join(category_path, file)
                        try:
                            with open(template_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            templates[category].append({
                                'name': file.replace('.template', ''),
                                'filename': file,
                                'content': content,
                                'path': template_path
                            })
                        except Exception as e:
                            logger.log_error(f"Could not read template {file}: {e}")
    
    return templates

# API Routes

@app.route('/api/status')
def api_status():
    """Get server status."""
    return jsonify({
        'status': 'running',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

@app.route('/api/config')
def api_config():
    """Get printer configuration."""
    config = load_config()
    if config:
        # Don't expose sensitive information
        safe_config = {
            'default_printer': config.get('default_printer'),
            'date_format': config.get('date_format'),
            'printers': list(config.get('printers', {}).keys())
        }
        return jsonify(safe_config)
    return jsonify({'error': 'Configuration not available'}), 500

@app.route('/api/templates')
def api_templates():
    """Get available templates."""
    return jsonify(get_templates())

@app.route('/api/print', methods=['POST'])
def api_print():
    """Print a label with the given parameters."""
    try:
        data = request.get_json()
        
        # Extract parameters
        message = data.get('message', '')
        border_message = data.get('border_message', '')
        count = int(data.get('count', 1))
        message_only = data.get('message_only', False)
        preview_only = data.get('preview_only', True)
        date_str = data.get('date', '')
        
        logger.log(f"API Print request: message='{message}', count={count}, preview_only={preview_only}")
        
        # Build command arguments
        args = []
        if message:
            args.extend(['-m', message])
        if border_message:
            args.extend(['-b', border_message])
        if message_only:
            args.append('-o')
        if date_str:
            args.extend(['-d', date_str])
        if count > 1:
            args.extend(['-c', str(count)])
        if preview_only:
            args.append('--preview-only')
        
        # Execute label printer
        label_printer_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "label-printer.py")
        command = ['python', label_printer_path] + args
        
        result = subprocess.run(command, capture_output=True, text=True, check=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        logger.log_success(f"Label printed successfully", f"Command: {' '.join(command)}")
        
        # Try to get the preview image
        preview_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "label_preview.png")
        preview_available = os.path.exists(preview_path)
        
        return jsonify({
            'success': True,
            'message': 'Label processed successfully',
            'output': result.stdout,
            'preview_available': preview_available,
            'preview_url': '/api/preview' if preview_available else None
        })
        
    except subprocess.CalledProcessError as e:
        error_msg = f"Label printing failed: {e.stderr}"
        logger.log_error(error_msg)
        return jsonify({
            'success': False,
            'error': error_msg,
            'stdout': e.stdout,
            'stderr': e.stderr
        }), 500
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.log_error(error_msg)
        return jsonify({
            'success': False,
            'error': error_msg
        }), 500

@app.route('/api/preview')
def api_preview():
    """Get the latest label preview image."""
    preview_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "label_preview.png")
    if os.path.exists(preview_path):
        return send_from_directory(
            os.path.dirname(preview_path),
            "label_preview.png",
            mimetype='image/png'
        )
    return jsonify({'error': 'No preview available'}), 404

@app.route('/api/logs')
def api_logs():
    """Get recent log entries."""
    try:
        log_entries = []
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
        
        # Find the most recent log directory
        if os.path.exists(logs_dir):
            # This is a simplified approach - you might want to implement more sophisticated log retrieval
            for year in sorted(os.listdir(logs_dir), reverse=True)[:1]:  # Just the most recent year
                year_path = os.path.join(logs_dir, year)
                if os.path.isdir(year_path):
                    for month in sorted(os.listdir(year_path), reverse=True)[:1]:  # Most recent month
                        month_path = os.path.join(year_path, month)
                        if os.path.isdir(month_path):
                            for day in sorted(os.listdir(month_path), reverse=True)[:1]:  # Most recent day
                                day_path = os.path.join(month_path, day, "runs")
                                if os.path.exists(day_path):
                                    for run in sorted(os.listdir(day_path), reverse=True)[:5]:  # Last 5 runs
                                        log_file = os.path.join(day_path, run, "log.txt")
                                        if os.path.exists(log_file):
                                            with open(log_file, 'r', encoding='utf-8') as f:
                                                content = f.read()
                                            log_entries.append({
                                                'timestamp': run,
                                                'date': day,
                                                'content': content
                                            })
        
        return jsonify({
            'logs': log_entries[:10]  # Return up to 10 most recent log entries
        })
    except Exception as e:
        return jsonify({'error': f'Could not retrieve logs: {str(e)}'}), 500

# Web Interface Routes

@app.route('/')
def index():
    """Serve the main web interface."""
    return send_from_directory('static', 'index.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files."""
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    return send_from_directory(static_dir, filename)

# Legacy API endpoint for compatibility
@app.route('/app/date-printer', methods=['GET'])
def legacy_date_printer():
    """Legacy endpoint for backwards compatibility."""
    count_str = request.args.get('count', '1')
    try:
        count_val = int(count_str)
        if count_val <= 0:
            raise ValueError("Count must be positive.")
    except ValueError:
        return Response("Error: Invalid 'count' parameter. Must be a positive integer.", 
                       status=400, mimetype='text/plain')
    
    # Redirect to new API
    return jsonify({
        'message': 'This endpoint is deprecated. Please use the web interface at / or the API at /api/print',
        'redirect': '/',
        'count': count_val
    })

if __name__ == '__main__':
    PORT = 5000
    HOST_IP = get_local_ip()
    
    logger.log("Starting Label Printer Web Server")
    logger.log(f"Server will be available at:")
    logger.log(f"  Local: http://127.0.0.1:{PORT}")
    logger.log(f"  Network: http://{HOST_IP}:{PORT}")
    
    print("=" * 60)
    print("Label Printer Web Server")
    print("=" * 60)
    print(f"Local URL:      http://127.0.0.1:{PORT}")
    print(f"Network URL:    http://{HOST_IP}:{PORT}")
    print(f"Web Interface:  http://{HOST_IP}:{PORT}")
    print(f"API Status:     http://{HOST_IP}:{PORT}/api/status")
    print("=" * 60)
    print()
    
    # Create static directory if it doesn't exist
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    os.makedirs(static_dir, exist_ok=True)
    
    try:
        app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
    except KeyboardInterrupt:
        logger.log("Server stopped by user")
        print("\nServer stopped.")
    except Exception as e:
        logger.log_error(f"Server error: {e}")
        print(f"Server error: {e}")