# Fact-Checking Backend System

A comprehensive Django backend for fact-checking claims using ChatGPT API, Google Search API, and Crawl4ai for web content extraction.

## 🚀 Features

- **Multi-step Analysis**: Automated fact-checking workflow with ChatGPT integration
- **Source Discovery**: Google Search API integration for finding credible sources
- **Content Extraction**: Crawl4ai-powered web scraping and content analysis
- **Real-time Updates**: WebSocket support for live progress tracking
- **Asynchronous Processing**: Celery-based task queue for scalable analysis
- **Comprehensive API**: RESTful endpoints for all fact-checking operations
- **Source Evaluation**: Automated credibility scoring and bias assessment
- **Structured Results**: Detailed verdicts with supporting evidence

## 📋 Prerequisites

- Python 3.8+
- Redis server (for Celery and WebSocket support)
- OpenAI API key
- Google Custom Search API key and Search Engine ID

## 🛠️ Installation

### 1. Clone and Setup Environment

```bash
# Clone the repository
git clone <your-repo-url>
cd factcheck-backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your settings
nano .env
```

Required environment variables:
```env
DJANGO_SECRET_KEY=your-secret-key-here
DEBUG=True

# API Keys
OPENAI_API_KEY=your-openai-api-key-here
GOOGLE_SEARCH_API_KEY=your-google-search-api-key-here
GOOGLE_SEARCH_ENGINE_ID=your-google-search-engine-id-here

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# CORS Configuration
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

### 3. Database Setup

```bash
# Create and run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser
```

### 4. Start Redis Server

```bash
# Install Redis (Ubuntu/Debian)
sudo apt update
sudo apt install redis-server

# Start Redis
sudo systemctl start redis-server

# On macOS with Homebrew
brew install redis
brew services start redis
```

### 5. Start Services

#### Terminal 1: Django Development Server
```bash
python manage.py runserver
```

#### Terminal 2: Celery Worker
```bash
celery -A factcheck_backend worker --loglevel=info
```

#### Terminal 3: Celery Beat (for periodic tasks)
```bash
celery -A factcheck_backend beat --loglevel=info
```

## 🔧 API Endpoints

### Main Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/fact-check/` | Create new fact-check session |
| GET | `/api/fact-check/{session_id}/status/` | Get analysis progress |
| GET | `/api/fact-check/{session_id}/results/` | Get detailed results |
| GET | `/api/fact-check/{session_id}/steps/` | Get analysis steps |
| GET | `/api/fact-check/list/` | List recent sessions |
| DELETE | `/api/fact-check/{session_id}/delete/` | Delete session |
| GET | `/api/health/` | Health check |

### WebSocket Endpoint
- `ws://localhost:8000/ws/fact-check/{session_id}/` - Real-time updates

## 📝 Usage Examples

### 1. Create Fact-Check Session

```bash
curl -X POST http://localhost:8000/api/fact-check/ \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "The Earth is flat and NASA is lying about it."
  }'
```

Response:
```json
{
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "pending",
  "message": "Fact-check analysis started"
}
```

### 2. Check Analysis Status

```bash
curl http://localhost:8000/api/fact-check/123e4567-e89b-12d3-a456-426614174000/status/
```

### 3. Get Results

```bash
curl http://localhost:8000/api/fact-check/123e4567-e89b-12d3-a456-426614174000/results/
```

### 4. Upload Image with Text

```bash
curl -X POST http://localhost:8000/api/fact-check/ \
  -F "user_input=Check this screenshot for misinformation" \
  -F "uploaded_image=@screenshot.png"
```

## 🧪 Testing

### Test the System

```bash
# Test with default claim
python manage.py test_factcheck

# Test with custom claim
python manage.py test_factcheck --claim "COVID-19 vaccines contain microchips"

# Test asynchronously
python manage.py test_factcheck --async --claim "The moon landing was fake"

# Check session status
python manage.py check_session <session-id>
```

### Run Unit Tests

```bash
python manage.py test
```

## 🏗️ Architecture Overview

### Component Structure

```
factcheck-backend/
├── apps/
│   ├── api/              # REST API endpoints and WebSocket consumers
│   ├── fact_checker/     # Core fact-checking logic and models
│   │   ├── services/     # External service integrations
│   │   ├── models.py     # Database models
│   │   └── tasks.py      # Celery tasks
│   └── core/             # Shared utilities and middleware
├── factcheck_backend/    # Django project configuration
└── requirements.txt      # Python dependencies
```

### Analysis Workflow

1. **Initial Analysis** (ChatGPT): Parse claim and identify key topics
2. **Source Discovery** (Google Search): Find relevant sources
3. **Content Extraction** (Crawl4ai): Extract and clean web content
4. **Source Evaluation** (ChatGPT): Assess credibility and relevance
5. **Final Verdict** (ChatGPT): Generate comprehensive fact-check result

### Database Models

- **FactCheckSession**: Main session tracking
- **AnalysisStep**: Individual workflow steps
- **Source**: Discovered and analyzed sources
- **SearchQuery**: Search queries and results
- **ChatGPTInteraction**: API interaction logs

## 🔒 Security Considerations

1. **API Keys**: Store in environment variables, never commit to code
2. **Rate Limiting**: Implement rate limiting for production use
3. **Input Validation**: All user inputs are validated and sanitized
4. **CORS**: Configure allowed origins appropriately
5. **Authentication**: Add authentication for production deployment

## 🚀 Production Deployment

### Environment Setup

1. Set `DEBUG=False` in production
2. Configure proper database (PostgreSQL recommended)
3. Set up Redis for production use
4. Configure proper logging
5. Set up SSL/HTTPS

### Docker Deployment

```dockerfile
# Example Dockerfile
FROM python:3.9

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["gunicorn", "factcheck_backend.wsgi:application", "--bind", "0.0.0.0:8000"]
```

### Environment Variables for Production

```env
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DATABASE_URL=postgresql://user:password@localhost:5432/factcheck_prod
REDIS_URL=redis://localhost:6379/0
CORS_ALLOWED_ORIGINS=https://yourdomain.com
```

## 📊 Monitoring and Logging

### Logging Configuration

The system includes comprehensive logging:
- API request/response logging
- Analysis step tracking
- Error logging with stack traces
- Performance metrics

### Celery Monitoring

Use Celery Flower for task monitoring:
```bash
pip install flower
celery -A factcheck_backend flower
```

## 🤝 Integration with Frontend

### Vue.js Frontend Integration

```javascript
// Example WebSocket connection
const socket = new WebSocket(`ws://localhost:8000/ws/fact-check/${sessionId}/`);

socket.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'progress_update') {
    updateProgressBar(data.progress.progress_percentage);
  } else if (data.type === 'analysis_complete') {
    displayResults(data.result);
  }
};
```

### API Integration

```javascript
// Create fact-check session
const response = await fetch('/api/fact-check/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ user_input: claim })
});

const { session_id } = await response.json();

// Get results
const results = await fetch(`/api/fact-check/${session_id}/results/`);
```

## 🐛 Troubleshooting

### Common Issues

1. **Redis Connection Error**: Ensure Redis server is running
2. **API Key Errors**: Verify OpenAI and Google API keys are valid
3. **WebSocket Issues**: Check Redis and Channels configuration
4. **Celery Task Failures**: Check worker logs and Redis connection

### Debug Mode

Enable detailed logging:
```env
LOG_LEVEL=DEBUG
```

### Check System Health

```bash
curl http://localhost:8000/api/health/
```

## 📈 Performance Optimization

1. **Caching**: Implement Redis caching for repeated queries
2. **Database Indexing**: Add indexes for frequently queried fields
3. **Task Queue**: Use multiple Celery workers for parallel processing
4. **Content Limits**: Limit content extraction size
5. **Rate Limiting**: Implement API rate limiting

## 🔄 Updates and Maintenance

### Regular Maintenance Tasks

1. **Cleanup Old Sessions**: Automatic via Celery beat
2. **Update Dependencies**: Regular security updates
3. **Monitor API Usage**: Track API costs and usage
4. **Database Maintenance**: Regular backups and optimization

## 📚 Additional Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Google Custom Search API](https://developers.google.com/custom-search/v1/overview)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

**Note**: This is a comprehensive fact-checking system designed for educational and research purposes. Always verify critical information through multiple reliable sources.
