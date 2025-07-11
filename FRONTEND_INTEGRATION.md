# Frontend Integration Guide

## 🔗 API Integration for Vue.js Frontend

This guide shows how to integrate your Vue.js fact-checking frontend with the Django backend APIs.

## 🆕 NEW: Research Service Integration

The backend now supports **two distinct modes**:
- **Fact Check Mode** (`fact_check`): Structured fact-checking with verdicts and confidence scores
- **Research Mode** (`research`): General research with markdown-formatted reports

## 📡 Base Configuration

```javascript
// api/config.js
const API_BASE_URL = process.env.VUE_APP_API_URL || 'http://localhost:8000/api'
const WS_BASE_URL = process.env.VUE_APP_WS_URL || 'ws://localhost:8000/ws'

export { API_BASE_URL, WS_BASE_URL }
```

## 🚀 Core API Endpoints

### 1. Create Fact-Check/Research Session

**Endpoint:** `POST /api/fact-check/`

**Request:**
```javascript
// Text-only fact-check (existing behavior)
{
  "user_input": "The Earth is flat and NASA is lying about it.",
  "mode": "fact_check"  // optional, defaults to "fact_check"
}

// Research mode (NEW)
{
  "user_input": "What are the latest developments in renewable energy?",
  "mode": "research"  // enables research mode
}

// With image upload
FormData with:
- user_input: "Check this screenshot for misinformation"
- uploaded_image: File object
- mode: "fact_check" or "research"
```

**Response:**
```javascript
{
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "pending",
  "message": "Analysis started",
  "session_data": {
    "session_id": "123e4567-e89b-12d3-a456-426614174000",
    "user_input": "The Earth is flat...",
    "mode": "fact_check",  // or "research"
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

## 🧪 Research Mode Integration

### Key Differences Between Modes

#### Input Expectations

**Fact Check Mode:**
- Specific claims or statements to verify
- Example: "The Earth is flat and NASA is lying about it"
- Example: "COVID-19 vaccines contain microchips"

**Research Mode:**
- Questions or topics to investigate
- Example: "What are the latest developments in renewable energy?"
- Example: "How does artificial intelligence impact healthcare?"

#### Response Format Differences

**Fact Check Response:**
```javascript
{
  "session_id": "uuid-here",
  "status": "completed",
  "final_verdict": "FALSE",           // TRUE/FALSE/PARTIALLY_TRUE/INSUFFICIENT_EVIDENCE
  "confidence_score": 0.85,           // 0.0 to 1.0
  "analysis_summary": "The claim that the Earth is flat contradicts overwhelming scientific evidence..."
}
```

**Research Response:**
```javascript
{
  "session_id": "uuid-here",
  "status": "completed",
  "final_verdict": null,              // Always null for research
  "confidence_score": null,           // Always null for research
  "analysis_summary": "# Research Report: Renewable Energy Developments\n\n## Executive Summary\n\nThis report examines the latest developments in renewable energy technologies...\n\n## Key Findings\n\n- Solar panel efficiency has improved by 15% in the past year\n- Wind energy costs have decreased by 20%\n- Battery storage technology shows promising advances\n\n## Detailed Analysis\n\n### Solar Energy\n\nRecent breakthroughs in perovskite solar cells have demonstrated...\n\n### Wind Energy\n\nOffshore wind installations have increased significantly...\n\n### Policy Implications\n\nGovernment incentives continue to drive adoption...\n\n## Conclusion\n\nThe renewable energy sector shows strong momentum..."
}
```

### Frontend Implementation Guide

#### 1. Mode Selection Component

```javascript
// components/ModeSelector.vue
<template>
  <div class="mode-selector">
    <div class="mode-buttons">
      <button 
        :class="{ active: mode === 'fact_check' }"
        @click="$emit('update:mode', 'fact_check')"
      >
        🔍 Fact Check
      </button>
      <button 
        :class="{ active: mode === 'research' }"
        @click="$emit('update:mode', 'research')"
      >
        📚 Research
      </button>
    </div>
    <p class="mode-description">
      {{ modeDescription }}
    </p>
  </div>
</template>

<script>
export default {
  props: {
    mode: {
      type: String,
      default: 'fact_check'
    }
  },
  computed: {
    modeDescription() {
      return this.mode === 'fact_check' 
        ? 'Verify the accuracy of specific claims with evidence-based analysis'
        : 'Get comprehensive research reports on topics and questions'
    }
  }
}
</script>
```

#### 2. Dynamic Input Component

```javascript
// components/InputForm.vue
<template>
  <form @submit.prevent="handleSubmit">
    <div class="input-group">
      <textarea
        v-model="userInput"
        :placeholder="placeholder"
        :rows="mode === 'research' ? 3 : 2"
        required
      />
      <div class="input-actions">
        <input
          type="file"
          accept="image/*"
          @change="handleFileUpload"
          ref="fileInput"
        />
        <button type="submit" :disabled="!userInput.trim() || loading">
          {{ submitButtonText }}
        </button>
      </div>
    </div>
  </form>
</template>

<script>
export default {
  props: {
    mode: String,
    loading: Boolean
  },
  data() {
    return {
      userInput: '',
      selectedFile: null
    }
  },
  computed: {
    placeholder() {
      return this.mode === 'fact_check'
        ? 'Enter a specific claim to fact-check (e.g., "The Earth is flat")'
        : 'Enter your research question or topic (e.g., "What are the benefits of renewable energy?")';
    },
    submitButtonText() {
      if (this.loading) return 'Processing...';
      return this.mode === 'fact_check' ? 'Start Fact Check' : 'Start Research';
    }
  },
  methods: {
    handleFileUpload(event) {
      this.selectedFile = event.target.files[0];
    },
    handleSubmit() {
      this.$emit('submit', {
        userInput: this.userInput,
        file: this.selectedFile,
        mode: this.mode
      });
    }
  }
}
</script>
```

#### 3. Results Display Component

```javascript
// components/ResultsDisplay.vue
<template>
  <div class="results-container">
    <div v-if="session.status === 'pending'" class="loading">
      <div class="spinner"></div>
      <p>{{ loadingMessage }}</p>
    </div>
    
    <div v-else-if="session.status === 'completed'" class="results">
      <!-- Fact Check Results -->
      <div v-if="mode === 'fact_check'" class="fact-check-results">
        <div class="verdict-section">
          <h2>Verdict</h2>
          <div :class="['verdict', verdictClass]">
            {{ formatVerdict(session.final_verdict) }}
          </div>
          <div class="confidence">
            Confidence: {{ (session.confidence_score * 100).toFixed(1) }}%
          </div>
        </div>
        
        <div class="analysis-section">
          <h3>Analysis Summary</h3>
          <div class="summary-content">
            {{ session.analysis_summary }}
          </div>
        </div>
      </div>
      
      <!-- Research Results -->
      <div v-else class="research-results">
        <div class="research-report">
          <div v-html="renderedMarkdown" class="markdown-content"></div>
        </div>
      </div>
    </div>
    
    <div v-else-if="session.status === 'error'" class="error">
      <h3>Analysis Error</h3>
      <p>{{ session.analysis_summary || 'An error occurred during analysis' }}</p>
    </div>
  </div>
</template>

<script>
import { marked } from 'marked';

export default {
  props: {
    session: Object,
    mode: String
  },
  computed: {
    loadingMessage() {
      return this.mode === 'fact_check' 
        ? 'Analyzing claim and gathering evidence...'
        : 'Researching your topic and compiling information...';
    },
    verdictClass() {
      const verdict = this.session.final_verdict?.toLowerCase();
      return {
        'verdict-true': verdict === 'true',
        'verdict-false': verdict === 'false',
        'verdict-partial': verdict === 'partially_true',
        'verdict-insufficient': verdict === 'insufficient_evidence'
      };
    },
    renderedMarkdown() {
      return marked(this.session.analysis_summary || '');
    }
  },
  methods: {
    formatVerdict(verdict) {
      const verdictMap = {
        'TRUE': 'True',
        'FALSE': 'False',
        'PARTIALLY_TRUE': 'Partially True',
        'INSUFFICIENT_EVIDENCE': 'Insufficient Evidence'
      };
      return verdictMap[verdict] || verdict;
    }
  }
}
</script>
```

#### 4. API Service Updates

```javascript
// services/apiService.js
class FactCheckAPI {
  constructor(baseURL) {
    this.baseURL = baseURL;
  }

  async submitRequest(userInput, file = null, mode = 'fact_check') {
    const formData = new FormData();
    formData.append('user_input', userInput);
    formData.append('mode', mode);
    
    if (file) {
      formData.append('uploaded_image', file);
    }
    
    try {
      const response = await fetch(`${this.baseURL}/fact-check/`, {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  async getSessionStatus(sessionId) {
    const response = await fetch(`${this.baseURL}/fact-check/${sessionId}/status/`);
    return await response.json();
  }

  async getSessionResults(sessionId) {
    const response = await fetch(`${this.baseURL}/fact-check/${sessionId}/results/`);
    return await response.json();
  }

  // Unified polling method for both modes
  async pollForResults(sessionId, onUpdate, maxAttempts = 60) {
    let attempts = 0;
    
    const poll = async () => {
      try {
        const result = await this.getSessionStatus(sessionId);
        onUpdate(result);
        
        if (result.status === 'completed' || result.status === 'error') {
          return result;
        }
        
        if (attempts >= maxAttempts) {
          throw new Error('Polling timeout');
        }
        
        attempts++;
        setTimeout(poll, 2000); // Poll every 2 seconds
      } catch (error) {
        console.error('Polling error:', error);
        throw error;
      }
    };
    
    return poll();
  }
}

export default FactCheckAPI;
```

#### 5. Complete Vue.js Integration Example

```javascript
// views/FactCheckResearch.vue
<template>
  <div class="fact-check-research-app">
    <div class="header">
      <h1>AI-Powered Fact Checking & Research</h1>
      <ModeSelector v-model:mode="selectedMode" />
    </div>
    
    <div class="main-content">
      <InputForm 
        :mode="selectedMode"
        :loading="isLoading"
        @submit="handleSubmit"
      />
      
      <ResultsDisplay 
        v-if="currentSession"
        :session="currentSession"
        :mode="selectedMode"
      />
    </div>
  </div>
</template>

<script>
import FactCheckAPI from '@/services/apiService';
import ModeSelector from '@/components/ModeSelector.vue';
import InputForm from '@/components/InputForm.vue';
import ResultsDisplay from '@/components/ResultsDisplay.vue';

export default {
  name: 'FactCheckResearch',
  components: {
    ModeSelector,
    InputForm,
    ResultsDisplay
  },
  data() {
    return {
      selectedMode: 'fact_check',
      currentSession: null,
      isLoading: false,
      api: new FactCheckAPI(process.env.VUE_APP_API_URL)
    };
  },
  methods: {
    async handleSubmit({ userInput, file, mode }) {
      this.isLoading = true;
      this.currentSession = null;
      
      try {
        // Submit request
        const response = await this.api.submitRequest(userInput, file, mode);
        this.currentSession = response.session_data;
        
        // Start polling for results
        await this.api.pollForResults(
          response.session_id,
          (updatedSession) => {
            this.currentSession = updatedSession;
          }
        );
        
      } catch (error) {
        console.error('Analysis failed:', error);
        this.currentSession = {
          status: 'error',
          analysis_summary: 'Failed to complete analysis. Please try again.'
        };
      } finally {
        this.isLoading = false;
      }
    }
  }
};
</script>

<style scoped>
.fact-check-research-app {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.header {
  text-align: center;
  margin-bottom: 30px;
}

.main-content {
  display: flex;
  flex-direction: column;
  gap: 30px;
}
</style>
```

### Testing Your Integration

Test both modes with appropriate inputs:

**Fact Check Test Cases:**
```javascript
// Good fact-check inputs
const factCheckTests = [
  "The Earth is flat",
  "COVID-19 vaccines contain microchips",
  "Climate change is caused by human activities",
  "The moon landing was faked"
];
```

**Research Test Cases:**
```javascript
// Good research inputs
const researchTests = [
  "What are the latest developments in artificial intelligence?",
  "How does renewable energy impact the economy?",
  "What are the health benefits of the Mediterranean diet?",
  "How do electric vehicles compare to gasoline cars?"
];
```

### Error Handling

Both modes use consistent error handling:

```javascript
function handleApiError(error, mode) {
  const modeText = mode === 'fact_check' ? 'fact-checking' : 'research';
  
  if (error.response) {
    // Server responded with error status
    return `${modeText} failed: ${error.response.data.error || 'Server error'}`;
  } else if (error.request) {
    // Request was made but no response
    return `${modeText} failed: No response from server`;
  } else {
    // Something else happened
    return `${modeText} failed: ${error.message}`;
  }
}
```

### Migration Notes

- **No Breaking Changes**: Existing fact-check functionality remains unchanged
- **Backward Compatible**: The `mode` parameter is optional and defaults to `fact_check`
- **Consistent API**: Same endpoints work for both modes
- **Null Handling**: Research mode returns `null` for `final_verdict` and `confidence_score`

## 📋 Quick Integration Checklist

### For Existing Fact-Check Applications

- [ ] Add mode selector UI component
- [ ] Update API calls to include `mode` parameter
- [ ] Handle `null` values for `final_verdict` and `confidence_score` in research mode
- [ ] Add markdown rendering for research results
- [ ] Update input placeholders based on selected mode
- [ ] Test both modes with appropriate sample inputs

### For New Applications

- [ ] Install markdown renderer (e.g., `marked` or `vue-markdown`)
- [ ] Implement mode selection in your UI
- [ ] Set up API service with mode support
- [ ] Create separate display components for each mode
- [ ] Add error handling for both modes
- [ ] Configure polling for real-time updates

## 🔧 Required Dependencies

```bash
# For Vue.js applications
npm install marked
# or
npm install vue-markdown

# For React applications
npm install react-markdown
```

## 📞 Support

If you encounter issues integrating the research service:

1. **Check your API requests** - Ensure the `mode` parameter is being sent correctly
2. **Verify response handling** - Make sure your code handles `null` values appropriately
3. **Test markdown rendering** - Confirm your markdown renderer works with the research output
4. **Review error handling** - Both modes use the same error response format

For additional support, check the backend logs or contact the development team.

---

**Last Updated**: January 2025  
**API Version**: 1.0  
**Supported Modes**: fact_check, research
