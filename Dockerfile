FROM python:3.10-slim

WORKDIR /app

# Install system dependencies including ffmpeg
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir "mcp[cli]>=1.2.0" yt-dlp

# Copy the server script
COPY youtube_subtitles_server.py .

# Set the entrypoint
ENTRYPOINT ["python", "youtube_subtitles_server.py"]

# Document the exposed port (stdio transport doesn't use a port, but good for documentation)
LABEL org.opencontainers.image.description="YouTube Subtitle Downloader MCP Server"
LABEL org.opencontainers.image.source="https://github.com/setkyar/youtube-subtitles-mcp"