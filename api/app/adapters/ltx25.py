"""Minimal LTX-2.5 API client for video generation.

This adapter integrates with Azure Foundry's LTX-2.5 service to generate synchronized
audio-video clips from text prompts, replacing the ComfyUI-based Wan 2.2 workflow.

Uses Foundry's REST API for video generation with proper authentication.
"""

import json
import time
import uuid
import requests
import os
from pathlib import Path
from typing import Optional, Dict, Any

from ..config import AZURE_FOUNDRY_RESOURCE_NAME

# LTX-2.5 API endpoint
LTX_API_BASE = f"https://{AZURE_FOUNDRY_RESOURCE_NAME}.services.ai.azure.com"

def get_foundry_token():
    """Get Microsoft Entra ID token for Foundry authentication"""
    try:
        from azure.identity import DefaultAzureCredential
        credential = DefaultAzureCredential()
        token = credential.get_token("https://ai.azure.com/.default")
        return token.token
    except ImportError:
        # Fallback for testing without Azure dependencies
        return "TEST_TOKEN"

def upload_file(path: Path, name: str | None = None) -> str:
    """Upload a local file to Foundry storage (placeholder for now)"""
    # For LTX-2.5, we'll pass the file content directly in the API call
    # This is a placeholder for potential future file upload handling
    return str(path)

def generate_video(prompt: str, width: int, height: int, duration: int, 
                   negative_prompt: str = "", audio_prompt: str = "") -> Dict[str, Any]:
    """
    Generate video using LTX-2.5 through Azure Foundry API
    
    Args:
        prompt: Text prompt describing the video content
        width: Output width in pixels
        height: Output height in pixels
        duration: Video duration in seconds
        negative_prompt: What to avoid in generation
        audio_prompt: Audio description for synchronized audio
        
    Returns:
        Dictionary with generation result details
    """
    # Get authentication token
    token = get_foundry_token()
    
    # Prepare API endpoint
    endpoint = f"{LTX_API_BASE}/providers/falai/lightricks/ltx-2.5/text-to-video/fast"
    
    # Prepare request payload
    payload = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "duration": duration,
        "fps": 24,
        "negative_prompt": negative_prompt,
        "audio_prompt": audio_prompt if audio_prompt else prompt  # Use prompt as audio prompt if not specified
    }
    
    # Prepare headers
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Make API call
    response = requests.post(endpoint, json=payload, headers=headers, timeout=300)
    response.raise_for_status()
    
    return response.json()

def save_video(video_data: Dict[str, Any], output_path: Path) -> Path:
    """
    Save video from LTX-2.5 response to file
    
    Args:
        video_data: Response from LTX-2.5 API
        output_path: Path to save the video file
        
    Returns:
        Path to saved video file
    """
    # This is a simplified approach - in practice, you'd need to handle
    # the actual video URL or binary data from the API response
    # For now, we'll create a placeholder
    output_path.write_text(json.dumps(video_data, indent=2))
    return output_path

def run_ltx_workflow(prompt: str, width: int, height: int, duration: int,
                     negative_prompt: str = "", audio_prompt: str = "",
                     output_path: Path = None) -> Path:
    """
    Generate video using LTX-2.5 and save to output path
    
    This function mimics the ComfyUI.run() interface for compatibility
    """
    # Generate video
    result = generate_video(prompt, width, height, duration, negative_prompt, audio_prompt)
    
    # Save result (this is where you'd actually handle the video file)
    if output_path:
        save_video(result, output_path)
    
    return output_path

def free():
    """Placeholder for cleanup - LTX-2.5 doesn't need model unloading like ComfyUI"""
    pass

def interrupt():
    """Placeholder for interruption - LTX-2.5 doesn't support interruption like ComfyUI"""
    pass