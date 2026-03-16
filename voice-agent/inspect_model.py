import asyncio
import pyvts
import os
import json

async def main():
    # Setup VTS plugin info
    base_dir = os.path.dirname(os.path.abspath(__file__))
    token_path = os.path.join(base_dir, "token.txt")
    
    plugin_info = {
        "plugin_name": "AURA-Agent",
        "developer": "Raygama",
        "authentication_token_path": token_path
    }

    # Initialize VTS
    vts = pyvts.vts(plugin_info=plugin_info, host="127.0.0.1", port=8001)
    
    print("Connecting to VTube Studio...")
    await vts.connect()
    
    print("Authenticating...")
    # Follow the controller's pattern: request token, then authenticate.
    await vts.request_authenticate_token()
    auth_res = await vts.request_authenticate()
    
    if not auth_res:
        print("ERROR: No response from VTube Studio authentication.")
        return

    if isinstance(auth_res, dict) and auth_res.get("messageType") == "APIError":
        print(f"ERROR: Authentication failed: {auth_res.get('data', {}).get('message')}")
        print("Please check VTube Studio and click 'Allow' if a popup appeared.")
        return

    # Request model info BEFORE using model_res
    model_res = await vts.request({
        "apiName": "VTubeStudioPublicAPI",
        "apiVersion": "1.0",
        "requestID": "getModelInfo",
        "messageType": "CurrentModelRequest"
    })

    output_file = os.path.join(base_dir, "model_parameters.json")
    print(f"Writing results to {output_file}...")

    results = {
        "model_name": model_res.get("data", {}).get("modelName"),
        "model_id": model_res.get("data", {}).get("modelID"),
        "parameters": []
    }

    # 2. Get available parameters
    params_res = await vts.request({
        "apiName": "VTubeStudioPublicAPI",
        "apiVersion": "1.0",
        "requestID": "getParams",
        "messageType": "InputParameterListRequest"
    })
    
    if params_res.get("messageType") == "APIError":
        print(f"ERROR: Could not fetch parameters: {params_res.get('data', {}).get('message')}")
        return

    params = params_res.get("data", {}).get("customParameters", []) + \
             params_res.get("data", {}).get("defaultParameters", [])
             
    for p in params:
        results["parameters"].append({
            "name": p.get("name"),
            "value": p.get("value"),
            "min": p.get("min"),
            "max": p.get("max")
        })

    # 3. Get available hotkeys
    hk_res = await vts.request({
        "apiName": "VTubeStudioPublicAPI",
        "apiVersion": "1.0",
        "requestID": "getHotkeys",
        "messageType": "HotkeysInCurrentModelRequest"
    })
    
    results["hotkeys"] = hk_res.get("data", {}).get("availableHotkeys", [])

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"Success! Please read {output_file}")
    
    # 4. Debug print specific parameter search
    print("\n--- Search Results for 'Tongue' or 'Mouth' ---")
    for p in params:
        name = p.get("name")
        if "tongue" in name.lower() or "mouth" in name.lower():
            print(f"MATCH: {name} | Value: {p.get('value')} | Range: {p.get('min')} to {p.get('max')}")

    await vts.close()

if __name__ == "__main__":
    asyncio.run(main())
