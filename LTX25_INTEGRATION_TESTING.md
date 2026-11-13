# Testing LTX-2.5 Integration

To test the LTX-2.5 integration with your musicvid project, follow these steps:

## Prerequisites

1. **Install Azure SDK dependencies** (only needed if you want to use real Azure authentication):
   ```bash
   pip install azure-identity
   ```

2. **Set up Azure Foundry**:
   - Deploy LTX-2.5 model in Azure Foundry
   - Configure your Azure subscription with proper permissions
   - Note your Foundry resource name

3. **Configure environment variables**:
   ```bash
   export AZURE_FOUNDRY_RESOURCE_NAME=your-resource-name
   ```

## Testing the Integration

1. **Run a test job with LTX-2.5**:
   ```bash
   # Set motion mode to 'draft' or 'final' to trigger LTX-2.5
   curl -X POST http://localhost:8090/api/jobs \
     -H "Content-Type: application/json" \
     -d '{
       "song": "test-song.mp3",
       "params": {
         "motion": "draft"
       }
     }'
   ```

2. **Check logs**:
   ```bash
   docker compose logs -f api
   ```

3. **Monitor the video generation stage**:
   The video stage should now use LTX-2.5 instead of ComfyUI/Wan 2.2

## Troubleshooting

If you encounter issues:

1. **Missing Azure dependencies**:
   - The LTX-2.5 adapter has a fallback mechanism that uses a test token
   - This allows you to test the integration without Azure setup

2. **API connection issues**:
   - Verify your `AZURE_FOUNDRY_RESOURCE_NAME` is set correctly
   - Ensure your Azure subscription has proper access to Foundry services

3. **Test without Azure**:
   - The system will fall back to a test token if Azure SDK is not installed
   - This allows you to test the code structure without real API calls

## Expected Behavior

With LTX-2.5 integration:
- Video generation will be synchronized with audio
- Higher quality output (up to 4K resolution)
- Faster generation times compared to Wan 2.2
- 20-second clips per scene (vs 5-second clips with Wan 2.2)