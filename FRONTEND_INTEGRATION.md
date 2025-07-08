# Frontend Integration Guide

## 🔗 API Integration for Vue.js Frontend

This guide shows how to integrate your Vue.js fact-checking frontend with the Django backend APIs.

## 📡 Base Configuration

```javascript
// api/config.js
const API_BASE_URL = process.env.VUE_APP_API_URL || 'http://localhost:8000/api'
const WS_BASE_URL = process.env.VUE_APP_WS_URL || 'ws://localhost:8000/ws'

export { API_BASE_URL, WS_BASE_URL }
```

## 🚀 Core API Endpoints

### 1. Create Fact-Check Session

**Endpoint:** `POST /api/fact-check/`

**Request:**
```javascript
// Text-only fact-check
{
  "user_input": "The Earth is flat and NASA is lying about it."
}

// With image upload
FormData with:
- user_input: "Check this screenshot for misinformation"
- uploaded_image: File object
```

**Response:**
```javascript
{
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "pending",
  "message": "Fact-check analysis started",
  "session_data": {
    "session_id": "123e4567-e89b-12d3-a456-426614174000",
    "user_input": "The Earth is flat...",
    "status": "pending",
    "created_at": "2025-07-02T10:30:00Z"
  }
}
```

### 2. Check Analysis Status

**Endpoint:** `GET /api/fact-check/{session_id}/status/`

**Response:**
```javascript
{
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "analyzing",
  "progress_percentage": 60.0,
  "completed_steps": 3,
  "total_steps": 5,
  "failed_steps": 0,
  "current_step": {
    "step_number": 4,
    "description": "Evaluating source credibility",
    "step_type": "verification"
  },
  "steps": [
    {
      "step_number": 1,
      "step_type": "topic_analysis",
      "description": "Analyzing claim and identifying key topics",
      "status": "completed",
      "completed_at": "2025-07-02T10:31:00Z"
    }
    // ... more steps
  ]
}
```

### 3. Get Fact-Check Results

**Endpoint:** `GET /api/fact-check/{session_id}/results/`

**Response:**
```javascript
{
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "verdict": "false",
  "confidence_score": 0.92,
  "summary": "The claim that the Earth is flat contradicts overwhelming scientific evidence...",
  "reasoning": "Multiple lines of evidence from astronomy, physics, and direct observation...",
  "key_evidence": [
    "Satellite imagery shows Earth's curvature",
    "Ships disappear hull-first over horizon",
    "Different star constellations visible from different latitudes"
  ],
  "supporting_evidence": [],
  "contradictory_evidence": [
    "NASA satellite images",
    "International Space Station footage",
    "Physics of gravity and planetary formation"
  ],
  "sources": [
    {
      "id": 1,
      "url": "https://nasa.gov/earth-photos",
      "title": "Earth Photos from Space",
      "publisher": "NASA",
      "credibility_score": 0.95,
      "supports_claim": false,
      "relevance_score": 0.98
    }
    // ... more sources
  ],
  "limitations": [
    "Analysis based on publicly available sources",
    "Some claims may require specialized scientific knowledge"
  ],
  "recommendations": [
    "Consult peer-reviewed scientific literature",
    "Review NASA and other space agency documentation"
  ],
  "created_at": "2025-07-02T10:30:00Z",
  "completed_at": "2025-07-02T10:35:00Z"
}
```

### 4. Get Analysis Steps (Debug/Transparency)

**Endpoint:** `GET /api/fact-check/{session_id}/steps/`

**Response:**
```javascript
{
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "analysis_steps": [
    {
      "step_number": 1,
      "step_type": "topic_analysis",
      "description": "Analyzing claim and identifying key topics",
      "status": "completed",
      "result_data": {
        "main_topic": "Earth shape and NASA conspiracy",
        "factual_claims": ["Earth is flat", "NASA is lying"],
        "complexity_score": 7
      },
      "started_at": "2025-07-02T10:30:15Z",
      "completed_at": "2025-07-02T10:31:00Z"
    }
    // ... more steps
  ],
  "search_queries": [
    {
      "query_text": "Earth flat NASA conspiracy",
      "search_type": "google",
      "results_count": 10
    }
  ],
  "sources_found": 15,
  "gpt_interactions": 5
}
```

### 5. List User Sessions

**Endpoint:** `GET /api/fact-check/list/`

**Query Parameters:**
- `page_size`: Number of results (max 100, default 20)
- `offset`: Pagination offset

**Response:**
```javascript
{
  "count": 3,
  "results": [
    {
      "session_id": "123e4567-e89b-12d3-a456-426614174000",
      "user_input": "The Earth is flat...",
      "status": "completed",
      "final_verdict": "false",
      "confidence_score": 0.92,
      "created_at": "2025-07-02T10:30:00Z"
    }
    // ... more sessions
  ]
}
```

### 6. Delete Session

**Endpoint:** `DELETE /api/fact-check/{session_id}/delete/`

**Response:**
```javascript
{
  "message": "Session deleted successfully",
  "session_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

### 7. Health Check

**Endpoint:** `GET /api/health/`

**Response:**
```javascript
{
  "status": "healthy",
  "message": "Fact-check API is running"
}
```

## 📡 WebSocket Integration

### Connection URL
```javascript
const websocketUrl = `ws://localhost:8000/ws/fact-check/${sessionId}/`
```

### WebSocket Messages

#### Incoming Message Types:

**Initial Status:**
```javascript
{
  "type": "initial_status",
  "data": {
    "session_id": "123e4567-e89b-12d3-a456-426614174000",
    "status": "analyzing",
    "progress_percentage": 20.0,
    "current_step": { /* step info */ }
  }
}
```

**Progress Update:**
```javascript
{
  "type": "update",
  "data": {
    "type": "progress_update",
    "progress": {
      "progress_percentage": 60.0,
      "current_step": {
        "step_number": 3,
        "description": "Extracting content from sources"
      }
    }
  }
}
```

**Step Update:**
```javascript
{
  "type": "update",
  "data": {
    "type": "step_update",
    "step_type": "crawl",
    "description": "Extracting content from 15 sources",
    "progress_percentage": 60.0,
    "timestamp": "2025-07-02T10:33:00Z"
  }
}
```

**Analysis Complete:**
```javascript
{
  "type": "update",
  "data": {
    "type": "analysis_complete",
    "result": {
      "success": true,
      "verdict": "false",
      "confidence_score": 0.92,
      "summary": "Analysis summary..."
    }
  }
}
```

**Error:**
```javascript
{
  "type": "update",
  "data": {
    "type": "analysis_error",
    "error": "OpenAI API rate limit exceeded"
  }
}
```

#### Outgoing Messages:

**Get Status:**
```javascript
{
  "type": "get_status"
}
```

**Ping:**
```javascript
{
  "type": "ping"
}
```

## 🛠️ Implementation Examples

### Basic API Service

```javascript
// services/factCheckService.js
import axios from 'axios'
import { API_BASE_URL } from './config'

class FactCheckService {
  async createSession(userInput, uploadedImage = null) {
    const formData = new FormData()
    formData.append('user_input', userInput)
    if (uploadedImage) {
      formData.append('uploaded_image', uploadedImage)
    }

    const response = await axios.post(`${API_BASE_URL}/fact-check/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return response.data
  }

  async getStatus(sessionId) {
    const response = await axios.get(`${API_BASE_URL}/fact-check/${sessionId}/status/`)
    return response.data
  }

  async getResults(sessionId) {
    const response = await axios.get(`${API_BASE_URL}/fact-check/${sessionId}/results/`)
    return response.data
  }

  async listSessions(pageSize = 20, offset = 0) {
    const response = await axios.get(`${API_BASE_URL}/fact-check/list/`, {
      params: { page_size: pageSize, offset }
    })
    return response.data
  }

  async deleteSession(sessionId) {
    const response = await axios.delete(`${API_BASE_URL}/fact-check/${sessionId}/delete/`)
    return response.data
  }
}

export default new FactCheckService()
```

### WebSocket Service

```javascript
// services/websocketService.js
import { WS_BASE_URL } from './config'

class WebSocketService {
  constructor() {
    this.socket = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
  }

  connect(sessionId, onMessage, onError = null) {
    const url = `${WS_BASE_URL}/fact-check/${sessionId}/`
    this.socket = new WebSocket(url)

    this.socket.onopen = () => {
      console.log('WebSocket connected')
      this.reconnectAttempts = 0
    }

    this.socket.onmessage = (event) => {
      const data = JSON.parse(event.data)
      onMessage(data)
    }

    this.socket.onclose = () => {
      console.log('WebSocket disconnected')
      this.attemptReconnect(sessionId, onMessage, onError)
    }

    this.socket.onerror = (error) => {
      console.error('WebSocket error:', error)
      if (onError) onError(error)
    }
  }

  sendMessage(message) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message))
    }
  }

  disconnect() {
    if (this.socket) {
      this.socket.close()
      this.socket = null
    }
  }

  attemptReconnect(sessionId, onMessage, onError) {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      setTimeout(() => {
        console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})`)
        this.connect(sessionId, onMessage, onError)
      }, 2000 * this.reconnectAttempts)
    }
  }
}

export default new WebSocketService()
```

## 🎯 Frontend Integration Points

### 1. Fact-Check Form Component
- Call `createSession()` API
- Handle both text and image uploads
- Show loading state during submission

### 2. Progress Tracking Component
- Connect to WebSocket for real-time updates
- Display progress bar and current step
- Handle connection errors gracefully

### 3. Results Display Component
- Fetch results using `getResults()` API
- Display verdict with appropriate styling
- Show sources, evidence, and confidence score

### 4. Session History Component
- Use `listSessions()` API with pagination
- Allow users to view past fact-checks
- Implement search and filtering

### 5. Error Handling
- Handle API errors (rate limits, server errors)
- Show user-friendly error messages
- Implement retry mechanisms

## 🔐 Security Considerations

### CORS Configuration
The backend is configured to allow requests from:
- `http://localhost:3000` (development)
- `http://127.0.0.1:3000` (development)

For production, update `CORS_ALLOWED_ORIGINS` in backend settings.

### Rate Limiting
Consider implementing client-side rate limiting to prevent excessive API calls.

### Input Validation
Always validate user input on the frontend before sending to the API.

## 📊 Response Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process response data |
| 201 | Created | Session created successfully |
| 400 | Bad Request | Show validation errors |
| 404 | Not Found | Session doesn't exist |
| 429 | Rate Limited | Show retry message |
| 500 | Server Error | Show generic error message |

## 🚀 Environment Configuration

```javascript
// .env.local (Vue.js)
VUE_APP_API_URL=http://localhost:8000/api
VUE_APP_WS_URL=ws://localhost:8000/ws

// .env.production
VUE_APP_API_URL=https://your-api-domain.com/api
VUE_APP_WS_URL=wss://your-api-domain.com/ws
```

This integration guide provides all the API endpoints and WebSocket connections needed to build a fully functional fact-checking frontend that communicates with your Django backend.
