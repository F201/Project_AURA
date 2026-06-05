# API Reference

The AURA ecosystem provides several internal and external REST/SSE endpoints. The **AI Service** acts as the central brain, while the **Token Server** handles authentication.

---

## AI Service (Brain)
**Base URL**: `http://localhost:8001`  
**Authentication**: Requires `Authorization: Bearer <INTERNAL_API_KEY>` for backend-to-backend calls.

### `POST /api/v1/chat/voice`
- **Description**: Triggered by the Voice Agent. Streams an expressive response with emotion tags.
- **Type**: Server-Sent Events (SSE)
- **Request Body**:
  ```json
  {
    "message": "User's transcribed text",
    "identity": "unique-user-id"
  }
  ```
- **Response**: A stream of JSON objects with text deltas, ending in `[DONE]`.

### `POST /api/v1/memory/session`
- **Description**: Initializes a conversation session and retrieves the user's Long-Term Memory (LTM).
- **Request Body**: `{"identity": "user-id"}`
- **Response**:
  ```json
  {
    "conversation_id": "uuid",
    "long_term_memory": "User's persistent context..."
  }
  ```

### `POST /api/v1/memory/extract`
- **Description**: Analyzes a finished chat interaction to extract new permanent facts (LTM).
- **Request Body**: `{"chat_text": "...", "identity": "..."}`

---

## Token Server
**Base URL**: `http://localhost:8082`

### `GET /getToken`
- **Description**: Generates a JWT for the frontend to connect to the LiveKit SFU.
- **Query Params**: `identity`, `room`
- **Response**: `{"token": "..."}`

---

## Swagger UI
You can access the interactive documentation directly in your browser while the service is running:
- **AI Service**: [http://localhost:8001/docs](http://localhost:8001/docs)
- **Token Server**: [http://localhost:8082/docs](http://localhost:8082/docs)
