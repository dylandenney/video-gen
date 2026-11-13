# Azure Foundry LTX v2.5 Fast API Integration for Musicvid

## API Endpoints for LTX v2.5 Fast

### Text-to-Video:
```
POST https://{FOUNDRY_RESOURCE_NAME}.services.ai.azure.com/providers/falai/lightricks/ltx-2.5/text-to-video/fast
```

### Image-to-Video:
```
POST https://{FOUNDRY_RESOURCE_NAME}.services.ai.azure.com/providers/falai/lightricks/ltx-2.5/image-to-video/fast
```

## Required Headers
```http
Authorization: Bearer ***
Content-Type: application/json
```

## Request Body Format
```json
{
  "prompt": "A cinematic scene of a person dancing to music with vibrant colors",
  "width": 1080,
  "height": 1920,
  "duration": 5,
  "fps": 24,
  "negative_prompt": "blurry, low quality, distorted"
}
```

## Integration Steps for Musicvid Video Stage

### 1. Update Environment Configuration
Add to your `.env` file:
```env
AZURE_FOUNDRY_RESOURCE_NAME=your-resource-name
AZURE_FOUNDRY_API_KEY=***
```

### 2. Create Authentication Helper
```python
# In api/app/adapters/foundry.py
import requests
from azure.identity import DefaultAzureCredential

def get_foundry_token():
    """Get Microsoft Entra ID token for Foundry authentication"""
    credential = DefaultAzureCredential()
    token = credential.get_token("https://ai.azure.com/.default")
    return token.token

def call_foundry_api(endpoint, payload):
    """Call Foundry API with proper authentication"""
    token = get_foundry_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    response = requests.post(endpoint, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()
```

### 3. Modify Video Stage Implementation
Update `api/app/stages/video.py` to use Foundry instead of local ComfyUI:

```python
# In video.py, replace ComfyUI calls with Foundry calls
def render_clip(job_dir, job):
    # Get scene data from storyboard
    scene = get_scene_data(job_dir, job)
    
    # Prepare prompt for Foundry
    prompt = f"{scene['description']} - {scene['camera_movement']}"
    
    # Foundry API call
    payload = {
        "prompt": prompt,
        "width": 1080,
        "height": 1920,  # 9:16 aspect ratio
        "duration": 5,   # 5 seconds per scene
        "fps": 24
    }
    
    endpoint = f"https://{os.getenv('AZURE_FOUNDRY_RESOURCE_NAME')}.services.ai.azure.com/providers/falai/lightricks/ltx-2.5/text-to-video/fast"
    
    # Call Foundry API
    result = call_foundry_api(endpoint, payload)
    
    # Download the generated video
    video_url = result['video_url']  # Assuming Foundry returns this
    # Save to clips directory
    save_video(job_dir, result['video_id'], video_url)
```

### 4. Update Dependencies
Add to your requirements.txt or Dockerfile:
```txt
azure-identity>=1.14.0
requests>=2.28.0
```

## Configuration Requirements

1. **Deploy LTX v2.5 Fast in Foundry**:
   - Use Azure CLI or portal to deploy the model
   - Ensure proper permissions for your identity

2. **Authentication Setup**:
   - Either use API key or Microsoft Entra ID
   - For local testing, use `az login` for Entra ID

3. **Billing Setup**:
   - Ensure your Azure subscription has the correct pricing tier
   - Monitor usage to avoid unexpected costs

## Migration Strategy

1. **Phase 1**: Keep current ComfyUI as fallback
2. **Phase 2**: Gradually switch to Foundry for video generation
3. **Phase 3**: Remove ComfyUI dependency entirely

This approach maintains backward compatibility while enabling access to superior video generation capabilities.