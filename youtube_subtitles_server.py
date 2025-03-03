from contextlib import asynccontextmanager
from typing import AsyncIterator
from mcp.server.fastmcp import FastMCP, Context
import mcp.types as types
import subprocess
import os
import tempfile
import re
import shutil
import sys

@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """
    Verify that yt-dlp is installed before starting the server.
    """
    # Check if yt-dlp is available
    yt_dlp_path = shutil.which("yt-dlp")
    
    if not yt_dlp_path:
        print("yt-dlp not found in PATH. Please install it: pip install yt-dlp", file=sys.stderr)
        yt_dlp_available = False
    else:
        print(f"Using yt-dlp at: {yt_dlp_path}", file=sys.stderr)
        yt_dlp_available = True
        
    # Try to update yt-dlp in the background
    if yt_dlp_available:
        try:
            subprocess.Popen(
                ["yt-dlp", "--update-to", "stable"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            # Ignore update errors
            pass
    
    try:
        yield {"yt_dlp_available": yt_dlp_available}
    finally:
        # Clean up if needed
        pass

# Create an MCP server with dependencies and lifespan
mcp = FastMCP(
    "YouTube Subtitle Downloader",
    dependencies=["yt-dlp>=2023.0.0"],
    lifespan=lifespan
)

def run_yt_dlp_command(args, cwd=None):
    """Run a yt-dlp command and return the result."""
    try:
        result = subprocess.run(
            ["yt-dlp"] + args,
            check=True,
            capture_output=True,
            text=True,
            cwd=cwd
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        error_message = e.stderr
        raise RuntimeError(f"yt-dlp error: {error_message}")
    except FileNotFoundError:
        raise RuntimeError("yt-dlp not found. Please make sure it's installed and in your PATH.")

@mcp.tool()
async def list_subtitle_languages(url: str, ctx: Context) -> str:
    """
    List available subtitle languages for a YouTube video.
    
    Args:
        url: URL of the YouTube video
        ctx: MCP context
        
    Returns:
        A formatted list of available subtitle languages
    """
    # Check if yt-dlp is available from lifespan context
    if not ctx.request_context.lifespan_context.get("yt_dlp_available", False):
        return "Error: yt-dlp is not installed. Please install it with: pip install yt-dlp"
    
    print(f"Fetching available subtitle languages for {url}", file=sys.stderr)
    
    try:
        # Use yt-dlp to list available subtitles
        output = run_yt_dlp_command([
            "--skip-download",
            "--list-subs",
            url
        ])
        
        # Parse the output to extract language information
        languages = []
        in_subtitles_section = False
        
        for line in output.splitlines():
            if "Available subtitles" in line:
                in_subtitles_section = True
                continue
                
            if in_subtitles_section and line.strip():
                # Look for language codes and names
                match = re.match(r'\s*(\w+)\s+(\w+)?\s*(.*)', line)
                if match:
                    lang_code = match.group(1)
                    lang_name = match.group(3).strip()
                    languages.append(f"{lang_code}: {lang_name}")
        
        if not languages:
            return "No subtitles found for this video."
            
        return "Available subtitle languages:\n" + "\n".join(languages)
    
    except Exception as e:
        print(f"Error listing subtitle languages: {str(e)}", file=sys.stderr)
        return f"Error listing subtitle languages: {str(e)}"

@mcp.tool()
async def download_subtitles(url: str, ctx: Context, lang: str = "en") -> str:
    """
    Download subtitles from a YouTube video.
    
    Args:
        url: URL of the YouTube video
        ctx: MCP context
        lang: Language code for subtitles (default: 'en' for English)
        
    Returns:
        The subtitles as text
    """
    # Check if yt-dlp is available from lifespan context
    if not ctx.request_context.lifespan_context.get("yt_dlp_available", False):
        return "Error: yt-dlp is not installed. Please install it with: pip install yt-dlp"
    
    ctx.info(f"Downloading {lang} subtitles for {url}")
    
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Define output format
        output_filename = os.path.join(temp_dir, "subtitles")
        
        try:
            # Run yt-dlp to download just the subtitles
            run_yt_dlp_command([
                "--skip-download",
                "--write-auto-sub",
                f"--sub-lang={lang}",
                "--convert-subs=srt",
                f"--output={output_filename}",
                url
            ], cwd=temp_dir)
            
            # Read the downloaded subtitle file
            subtitle_file = f"{output_filename}.{lang}.srt"
            
            if os.path.exists(os.path.join(temp_dir, subtitle_file)):
                with open(os.path.join(temp_dir, subtitle_file), "r", encoding="utf-8") as f:
                    subtitles = f.read()
                
                # Clean up SRT formatting to make it more readable
                # Remove timestamps and numbers
                cleaned_subtitles = re.sub(r'\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n', '', subtitles)
                # Remove empty lines
                cleaned_subtitles = re.sub(r'\n\s*\n', '\n', cleaned_subtitles)
                
                return cleaned_subtitles
            else:
                ctx.error(f"No subtitle file found: {subtitle_file}")
                return f"No subtitles found for language: {lang}"
                
        except Exception as e:
            ctx.error(f"Error downloading subtitles: {str(e)}")
            return f"Error downloading subtitles: {str(e)}"

@mcp.tool()
async def get_video_info(url: str, ctx: Context) -> str:
    """
    Get basic information about a YouTube video.
    
    Args:
        url: URL of the YouTube video
        ctx: MCP context
        
    Returns:
        Basic video information (title, duration, etc.)
    """
    # Check if yt-dlp is available from lifespan context
    if not ctx.request_context.lifespan_context.get("yt_dlp_available", False):
        return "Error: yt-dlp is not installed. Please install it with: pip install yt-dlp"
    
    print(f"Fetching video information for {url}", file=sys.stderr)
    
    try:
        # Run yt-dlp to get video info as JSON
        output = run_yt_dlp_command([
            "--skip-download",
            "--print", "%(title)s\n%(duration_string)s\n%(channel)s\n%(upload_date)s\n%(view_count)s",
            url
        ])
        
        # Parse the output
        lines = output.strip().split('\n')
        if len(lines) >= 5:
            title, duration, channel, upload_date, views = lines[:5]
            
            # Format upload date (YYYYMMDD to YYYY-MM-DD)
            if len(upload_date) == 8:
                upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
                
            info = f"Title: {title}\n"
            info += f"Duration: {duration}\n"
            info += f"Channel: {channel}\n"
            info += f"Upload Date: {upload_date}\n"
            info += f"Views: {views}"
            
            return info
        else:
            return f"Couldn't parse video information: {output}"
            
    except Exception as e:
        print(f"Error getting video info: {str(e)}", file=sys.stderr)
        return f"Error getting video info: {str(e)}"

@mcp.prompt()
def youtube_subtitles_workflow(url: str) -> list[types.PromptMessage]:
    """
    Create a workflow for analyzing YouTube video subtitles.
    
    Args:
        url: URL of the YouTube video
        
    Returns:
        A conversation to help analyze the video's subtitles
    """
    return [
        types.PromptMessage(
            role="user",
            content=types.TextContent(
                type="text",
                text=f"I want to analyze the subtitles from this YouTube video: {url}"
            )
        ),
        types.PromptMessage(
            role="user",
            content=types.TextContent(
                type="text",
                text="First, get basic information about the video."
            )
        ),
        types.PromptMessage(
            role="user",
            content=types.TextContent(
                type="text",
                text="Then, list available subtitle languages."
            )
        ),
        types.PromptMessage(
            role="user",
            content=types.TextContent(
                type="text",
                text="Finally, download the subtitles in my preferred language and analyze their content."
            )
        )
    ]

# Run the server if this file is executed directly
if __name__ == "__main__":
    mcp.run()