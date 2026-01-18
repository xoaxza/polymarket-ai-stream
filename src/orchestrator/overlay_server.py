"""Simple HTTP server to serve overlay files for LiveKit egress"""
import os
import asyncio
from pathlib import Path
from aiohttp import web
from aiohttp.web import Response

# Get overlay directory path (relative to project root)
PROJECT_ROOT = Path(__file__).parent.parent.parent
OVERLAY_DIR = PROJECT_ROOT / "overlays"

async def serve_overlay_file(request):
    """Serve overlay files with proper MIME types"""
    filename = request.match_info.get('filename', 'index.html')
    
    # Handle root route - serve index.html
    if not filename or filename == '':
        filename = 'index.html'
    
    # Security: only allow files from overlay directory
    file_path = OVERLAY_DIR / filename
    
    # Additional security: ensure file is within overlay directory (prevent path traversal)
    try:
        file_path.resolve().relative_to(OVERLAY_DIR.resolve())
    except ValueError:
        return Response(text="Invalid file path", status=403)
    
    if not file_path.exists() or not file_path.is_file():
        return Response(text=f"File not found: {filename}", status=404)
    
    # Determine MIME type
    mime_types = {
        '.html': 'text/html',
        '.css': 'text/css',
        '.js': 'application/javascript',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.svg': 'image/svg+xml',
    }
    
    ext = file_path.suffix.lower()
    content_type = mime_types.get(ext, 'application/octet-stream')
    
    # Read and serve file
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
        return Response(body=content, content_type=content_type)
    except Exception as e:
        return Response(text=f"Error reading file: {e}", status=500)

def create_overlay_app():
    """Create aiohttp application for serving overlays"""
    app = web.Application()
    
    # Route for index.html (default)
    app.router.add_get('/', lambda r: serve_overlay_file(r))
    app.router.add_get('/index.html', lambda r: serve_overlay_file(r))
    
    # Route for other files
    app.router.add_get('/{filename}', serve_overlay_file)
    
    return app

async def start_overlay_server(host='127.0.0.1', port=8080):
    """Start the overlay HTTP server
    
    Returns:
        tuple: (server, url) - The server instance and the base URL
    """
    app = create_overlay_app()
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, host, port)
    await site.start()
    
    url = f"http://{host}:{port}"
    print(f"📺 Overlay server started at {url}")
    print(f"   Serving files from: {OVERLAY_DIR}")
    
    return runner, url

async def stop_overlay_server(runner):
    """Stop the overlay server"""
    await runner.cleanup()
