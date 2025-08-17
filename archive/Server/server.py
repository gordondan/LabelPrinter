# server.py
from flask import Flask, Response, request
import subprocess
import socket
import html
import os
from werkzeug.middleware.proxy_fix import ProxyFix

# Initialize the Flask application
app = Flask(__name__)

# CRITICAL: Disable Werkzeug's host validation
import werkzeug.serving
werkzeug.serving.WSGIRequestHandler.address_string = lambda self: self.client_address[0]

# Fix for proxy headers when behind Nginx
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)


def get_local_ip():
    """
    Finds the local IP address of the machine.
    This is a common trick: connect to a public DNS server (like Google's)
    to find out which network interface is used for outbound traffic.
    No data is actually sent.
    """
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Doesn't have to be reachable
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1' # Fallback to localhost
    finally:
        if s:
            s.close()
    return ip

# Define the endpoint with the new path
@app.route('/app/date-printer', methods=['GET'])
# In server.py

@app.route('/app/date-printer', methods=['GET'])
def run_date_printer():
    """
    Executes date-printer.py, passing a '-c' flag with a 'count' parameter to it.
    The 'count' is retrieved from the URL's query string (e.g., ?count=3)
    """
    script_path = os.path.join(os.path.dirname(__file__), '..', 'DatePrinter', 'date_printer.py')
    
    # Get the 'count' parameter from the URL, default to '1' if not provided.
    count_str = request.args.get('count', '1')

    # Validate that the count is a positive integer.
    try:
        count_val = int(count_str)
        if count_val <= 0:
            raise ValueError("Count must be positive.")
    except ValueError:
        error_message = f"Error: Invalid 'count' parameter. Must be a positive integer."
        return Response(error_message, status=400, mimetype='text/plain')
    
    print(f"--- Received request to run '{script_path}' with count={count_val} ---")
    
    try:
        # --- THIS IS THE CORRECTED LINE ---
        # The command now includes the named flag '-c' before the value.
        command = ['python', script_path, '-c', str(count_val)]
        
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )

        print(f"--- Script {script_path} executed successfully ---")
        
        output_html = f"""
            <h1>Script Execution Successful</h1>
            <h2>Output from {script_path} (ran {count_val} time(s)):</h2>
            <pre>{html.escape(result.stdout)}</pre>
        """
        return Response(output_html, mimetype='text/html')

    except FileNotFoundError:
        print(f"--- ERROR: Script or Python interpreter not found. ---")
        error_message = f"Error: The script '{script_path}' or the Python interpreter was not found."
        return Response(error_message, status=500, mimetype='text/plain')

    except subprocess.CalledProcessError as e:
        print(f"--- ERROR: Script {script_path} returned a non-zero exit code. ---")
        error_html = f"""
            <h1>Script Execution Failed</h1>
            <p>The script returned an error (exit code {e.returncode}).</p>
            <h2>Standard Output:</h2>
            <pre>{html.escape(e.stdout)}</pre>
            <h2>Standard Error:</h2>
            <pre>{html.escape(e.stderr)}</pre>
        """
        return Response(error_html, status=500, mimetype='text/html')

if __name__ == '__main__':
    # Configuration
    PORT = 5000
    HOST_IP = get_local_ip()

    # Create the full URL for easy access
    full_url = f"http://{HOST_IP}:{PORT}/app/date-printer"
    
    print("--- Starting server... ---")
    print("\n" + "="*50)
    print("Server is running. Access it from any device on your network.")
    print(f"  > Localhost URL: http://127.0.0.1:{PORT}/app/date-printer")
    print(f"  > Network URL:   {full_url}")
    print(f"  > Public URL:    http://thunderbelly.duckdns.org/app/date-printer")
    print("\nTry adding a count parameter, for example:")
    print(f"  > {full_url}?count=3")
    print("="*50 + "\n")
    
    # Run Flask app with host validation disabled
    import sys
    
    # Completely disable host validation by patching the check
    original_check = werkzeug.serving.WSGIRequestHandler.address_string
    werkzeug.serving.WSGIRequestHandler.address_string = lambda self: '127.0.0.1'
    
    print("Starting Flask server with host validation disabled")
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)