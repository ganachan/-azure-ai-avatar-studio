# minimal_test.py
import os
import asyncio
from dotenv import load_dotenv

async def test_azure_connection():
    print("Loading environment...")
    load_dotenv()
    
    # Check if we have the basic requirements
    model_name = os.getenv('AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME')
    conn_string = os.getenv('AZURE_AI_AGENT_PROJECT_CONNECTION_STRING')
    
    if not model_name:
        print("ERROR: AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME not found")
        return
        
    if not conn_string:
        print("ERROR: AZURE_AI_AGENT_PROJECT_CONNECTION_STRING not found")
        return
        
    print(f"Model: {model_name}")
    print(f"Connection string: {conn_string[:50]}...")
    
    try:
        from azure.identity.aio import DefaultAzureCredential
        from semantic_kernel.agents import AzureAIAgent, AzureAIAgentSettings
        
        print("Testing Azure connection...")
        async with DefaultAzureCredential() as creds:
            print("Azure credentials created successfully")
            
        print("Test completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_azure_connection())