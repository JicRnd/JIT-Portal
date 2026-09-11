---
name: Configure LiteLLM Proxy Pipeline
description: Automated setup for the local Qwen3 routing chain
purpose: |
  This agent is responsible for setting up and configuring a LiteLLM proxy pipeline 
  to enable a two-stage LLM workflow where Qwen3 output is processed by a downstream 
  model like Llama3. The configuration must be done carefully to ensure the proxy 
  is properly initialized with the correct model definitions.
  The local gateway owns the sequential calls and exposes an
  OpenAI-compatible endpoint for chat clients.
---

# Configure LiteLLM Proxy Pipeline

## Overview
This agent will help set up a LiteLLM proxy pipeline for a two-stage LLM workflow where:
1. Qwen3-Coder (primary model) generates responses
2. A downstream model (like Llama3) processes/-sanitizes the output

## Instructions

### 1. Workspace Verification
- Verify that we're working in the correct workspace directory: `C:\Users\Kane\Documents\Projects\Cylinder_Quote_To_HTML`
- Confirm the current project structure and that we have access to required files
### 2. LiteLLM Installation Check
- Check if LiteLLM is already installed in the virtual environment (`Cylinder_Quote_Web_Milestone_1\.venv`)
- If not installed, confirm with user before installation
- Install LiteLLM only into the `.venv` directory using pip

### 3. Task Configuration
- Verify that the existing VS Code task `Start LiteLLM Proxy Agent` is correctly configured
- The task should use: `${workspaceFolder}/Cylinder_Quote_Web_Milestone_1/.venv/Scripts/python.exe`
- Ensure paths are consistent with actual workspace structure
- Start the local gateway in background; it uses `.vscode/config.yaml` for both Ollama model routes
- Test `/health` and `/health/liveliness` to ensure the gateway is running
- Test `/v1/models` and `/v1/chat/completions` to verify model discovery and a real local request
- Identify which VS Code extension is active for proper configuration

### 4. Two-Stage Contract
- `.vscode/chat_gateway.py` sends each request to Qwen3-Coder first, then sends the completed response to Llama3 for cleanup before returning it to the chat client.
- LiteLLM's `model_list` alone does not perform this chaining; do not replace the gateway with a model list and claim that sanitization still happens.
- If the sanitizer fails, the gateway returns the primary Qwen3 response and logs the failure.

## Files to Modify
- `.vscode/chat_gateway.py` (two-stage local gateway)
- `.vscode/config.yaml` (local Ollama model definitions)
- `.vscode/tasks.json` (gateway launch task)

## Required User Actions
1. Confirm installation of LiteLLM in virtual environment
2. Configure a compatible chat extension to use `http://localhost:8000/v1` and model `vscode-chat`
3. Do not change built-in GitHub Copilot settings unless the extension explicitly supports custom OpenAI-compatible endpoints