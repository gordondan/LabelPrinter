# Label Printer Web App

A modern, responsive web interface for the Label Printer system, built with Flask and vanilla JavaScript.

## Features

### 🖨️ Quick Print
- **Custom Messages**: Create labels with main message and optional border message
- **Date Control**: Use today's date or specify a custom date
- **Batch Printing**: Print multiple copies (1-99)
- **Message-Only Mode**: Create labels without date information
- **Preview Mode**: Generate preview without printing
- **Smart Font Sizing**: Automatically adjusts font size based on message length for optimal readability

### 📋 Templates
- **Template Library**: Use pre-configured templates from the `label-images` directory
- **Category Organization**: Templates organized by categories (family, office, personal, etc.)
- **Template Preview**: View and use existing templates
- **Dynamic Loading**: Templates loaded dynamically from the file system

### 📜 Activity Logs
- **Recent Activity**: View recent label printing operations
- **Detailed Logs**: See full log output with timestamps
- **Real-time Updates**: Refresh logs to see latest activity
- **Formatted Display**: Easy-to-read log format with timestamps

### ⚙️ Settings & Status
- **Server Status**: Real-time server status monitoring
- **Printer Configuration**: View available printers and settings
- **System Information**: Configuration details and system status
- **Error Handling**: Comprehensive error reporting and troubleshooting

## Installation & Setup

### Prerequisites
- Python 3.7 or higher
- Flask (`pip install flask`)
- All dependencies from the main Label Printer project

### Running the Server

1. **Start the Web Server**:
   ```bash
   cd Server
   python label_server.py
   ```

2. **Access the Web Interface**:
   - Local: http://127.0.0.1:5000
   - Network: http://[YOUR-IP]:5000

3. **API Endpoints**:
   - Status: http://127.0.0.1:5000/api/status
   - Print: POST http://127.0.0.1:5000/api/print
   - Config: http://127.0.0.1:5000/api/config
   - Templates: http://127.0.0.1:5000/api/templates
   - Logs: http://127.0.0.1:5000/api/logs
   - Preview: http://127.0.0.1:5000/api/preview

## API Usage

### Print API
Send POST requests to `/api/print` with JSON payload:

```json
{
    "message": "Your message here",
    "border_message": "Optional border text",
    "count": 1,
    "message_only": false,
    "preview_only": true,
    "date": "2025-08-09"
}
```

**Response**:
```json
{
    "success": true,
    "message": "Label processed successfully",
    "output": "Command output...",
    "preview_available": true,
    "preview_url": "/api/preview"
}
```

### Configuration API
GET `/api/config` returns:
```json
{
    "default_printer": "Munbyn RW402B",
    "date_format": "%B %d, %Y",
    "printers": ["Munbyn RW402B(Bluetooth)"]
}
```

## Design & Styling

The web interface uses a modern design system based on the todo-lists project:

### Color Palette
- **Primary Teal**: #00c4aa (main accent color)
- **Primary Blue**: #0099cc (secondary accent)
- **Dark Gray**: #2c3e50 (text and headers)
- **Light Gray**: #f8f9fa (backgrounds)

### Features
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Accessibility**: WCAG compliant with proper focus states and ARIA labels
- **Modern UI**: Clean, intuitive interface with smooth animations
- **Loading States**: Visual feedback during operations
- **Error Handling**: User-friendly error messages and recovery options

## File Structure

```
Server/
├── label_server.py          # Main Flask server application
├── static/                  # Web interface files
│   ├── index.html          # Main HTML interface
│   ├── style.css           # Modern CSS styling
│   └── app.js              # JavaScript functionality
└── README.md               # This documentation
```

## Font Sizing Improvements

The web app includes the improved font sizing algorithm that:
- **Prevents oversized fonts** for short messages
- **Scales appropriately** based on message length:
  - 1-2 characters: max 60px
  - 3-5 characters: max 55px
  - 6-10 characters: max 50px (like "Chicken")
  - 11-20 characters: max 35px
  - 20+ characters: max 25px
- **Preserves margins** for readability
- **Maintains proportions** relative to available space

## Logging Integration

The server creates comprehensive logs using the integrated logging system:
- **Timestamped sessions**: Each operation creates a timestamped log
- **Full command logging**: Complete record of all API calls
- **Preview images**: Label previews saved to log directories
- **Error tracking**: Detailed error logging for troubleshooting

## Development

### Adding New Features
1. **API Endpoints**: Add new routes in `label_server.py`
2. **Frontend**: Update HTML, CSS, and JavaScript in `/static/`
3. **Integration**: Connect new features to existing label printer functionality

### Customization
- **Styling**: Modify `static/style.css` for custom themes
- **Layout**: Update `static/index.html` for interface changes
- **Functionality**: Extend `static/app.js` for new features

### Debugging
- Enable Flask debug mode for development
- Check browser console for JavaScript errors
- Monitor server logs for API issues
- Use `/api/status` endpoint for server health checks

## Compatibility

- **Browsers**: Modern browsers with ES6+ support
- **Mobile**: Responsive design works on all screen sizes
- **Printers**: Compatible with all label printers supported by the main system
- **Operating Systems**: Works on Windows, macOS, and Linux

## Security Notes

- **Development Server**: The included Flask server is for development only
- **Production**: Use a production WSGI server (like Gunicorn) for deployment
- **Network Access**: Server binds to all interfaces (0.0.0.0) for network access
- **API Security**: Consider adding authentication for production use

## Troubleshooting

### Common Issues

1. **Server Won't Start**:
   - Check if port 5000 is available
   - Verify Python dependencies are installed
   - Check for Unicode encoding issues on Windows

2. **Labels Not Printing**:
   - Verify printer configuration in `printer-config.json`
   - Check printer connection and power
   - Use preview mode to test label generation

3. **Web Interface Not Loading**:
   - Check if static files are in the correct location
   - Verify server is running on correct port
   - Check browser console for JavaScript errors

4. **API Errors**:
   - Check server logs for detailed error messages
   - Verify JSON payload format for POST requests
   - Test with simple curl commands first

## Support

For issues and feature requests, refer to the main Label Printer project documentation and issue tracker.