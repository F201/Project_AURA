import asyncio
import pyvts
import os

async def main():
    # Use absolute path for token.txt
    base_dir = os.path.dirname(os.path.abspath(__file__))
    token_path = os.path.join(base_dir, "token.txt")
    
    plugin_info = {
        "plugin_name": "AURA-Agent",
        "developer": "Raygama",
        "authentication_token_path": token_path
    }
    
    # Ensure directory exists
    os.makedirs(base_dir, exist_ok=True)
    
    vts = pyvts.vts(plugin_info=plugin_info, host="127.0.0.1", port=8001)
    
    print("Connecting to VTube Studio...")
    print("IMPORTANT: Look for a popup in VTube Studio and click 'Allow' if prompted.")
    
    try:
        await vts.connect()
        await vts.request_authenticate_token()
        await vts.request_authenticate()
        
        response = await vts.request({
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": "checkHotkeys",
            "messageType": "HotkeysInCurrentModelRequest"
        })
        
        data = response.get("data", {})
        hotkeys = data.get("availableHotkeys", [])
        
        if not response.get("messageType") == "HotkeysInCurrentModelResponse":
            print(f"Unexpected response: {response}")
            return

        print("\n--- Available Hotkeys in VTube Studio ---")
        if not hotkeys:
            print("No hotkeys found in the CURRENT model.")
            print("Please make sure you have hotkeys set up in VTS (under the Keyboard icon tab).")
        
        for i, hk in enumerate(hotkeys, 1):
            name = hk.get('name', 'Unnamed')
            hk_id = hk.get('hotkeyID', 'No ID')
            file = hk.get('file', 'No File')
            print(f"[{i}] Name: {name}")
            print(f"    ID:   {hk_id}")
            print(f"    File: {file}")
            print("-" * 40)
            
        print("\nVerification Complete!")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await vts.close()

if __name__ == "__main__":
    asyncio.run(main())
