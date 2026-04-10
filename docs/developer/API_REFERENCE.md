# API Reference

The AURA Backend provides multiple HTTP/REST endpoints for programmatic interaction, operated via FastAPI on the `ai-service` and the lightweight auth `token-server`.

## AI Service Endpoints 
**Base URL**: `http://localhost:8000`

### `POST /api/v1/chat`
- **Description**: Primary interface for triggering a textual RAG query into the Supabase Memory database without invoking the Voice Agent.
- **Request Body**:
  ```json
  {
    "message": "What is the primary theme of the uploaded PDF?",
    "user_id": "optional-uuid"
  }
  ```
- **Response**: String containing the prompt + the RAG contextual chunks.

### `POST /api/v1/memory` (Document Ingestion)
- **Description**: Uploads a document to chunk and embed into the vector database.
- **Content-Type**: `multipart/form-data`
- **Parameters**: 
  - `file`: The `.txt`, `.pdf`, or `.pptx` file payload.
- **Response**: `200 OK` on successful parse and Supabase insertion.

---

## Token Server Endpoints
**Base URL**: `http://localhost:8082`

### `GET /getToken`
- **Description**: Requested by the frontend `livekit-client` upon instantiation to authorize access to the LiveKit Cloud websocket.
- **Response**:
  ```json
  {
    "token": "eyJhbGci..."
  }
  ```
