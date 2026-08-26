import urllib.request
import json
import sys
import os

def is_maintenance_active():
    """
    Checks the remote config. 
    Returns True if maintenance is active (status != ACTIVE), otherwise False.
    """
    try:
        url = "https://huggingface.co/datasets/love14/my-app-config/raw/main/core_config.json"
        
        # 🔒 Securely fetch the token from environment variables
        hf_token = os.environ.get("HF_TOKEN")
        
        headers = {}
        if not hf_token:
            print("⚠️ Warning: HF_TOKEN environment variable not found. Secure connection may fail.")
        else:
            headers = {"Authorization": f"Bearer {hf_token}"}
            
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode('utf-8'))
            
        if data.get("status") != "ACTIVE":
            print("\n⚠️ Mewar ERP Chatbot is currently under maintenance. We are performing some updates, please try again in a little while! 🙏\n")
            return True  # Maintenance is ACTIVE
            
        return False  # Status is ACTIVE, so no maintenance
            
    except Exception as e:
        print(f"❌ Direct Verification Error: {e}")
        # Default fallback: agar error aaye toh server chalne do
        return False 

# Agar aapko load_core_services bhi chahiye purane kisi code ke liye, toh use bhi rakh sakte hain
def load_core_services():
    if is_maintenance_active():
        sys.exit(1)