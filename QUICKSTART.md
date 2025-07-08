# Quick Start Guide for Fact-Checking Backend

## 🚀 Quick Setup (5 minutes)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables
Create a `.env` file with:
```env
OPENAI_API_KEY=your-openai-api-key
GOOGLE_SEARCH_API_KEY=your-google-api-key
GOOGLE_SEARCH_ENGINE_ID=your-search-engine-id
REDIS_URL=redis://localhost:6379/0
```

### 3. Setup Database
```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. Start Services (3 terminals)
```bash
# Terminal 1: Django server
python manage.py runserver

# Terminal 2: Celery worker
celery -A factcheck_backend worker --loglevel=info

# Terminal 3: Redis (if not running as service)
redis-server
```

## 🧪 Test the System

### Quick Test
```bash
python manage.py test_factcheck --claim "The Earth is flat"
```

### API Test
```bash
curl -X POST http://localhost:8000/api/fact-check/ \
  -H "Content-Type: application/json" \
  -d '{"user_input": "COVID-19 vaccines contain microchips"}'
```

## 📋 Key API Endpoints

- `POST /api/fact-check/` - Start fact-check
- `GET /api/fact-check/{id}/status/` - Check progress
- `GET /api/fact-check/{id}/results/` - Get results
- `GET /api/health/` - Health check

## 🔗 WebSocket Connection
```javascript
const ws = new WebSocket(`ws://localhost:8000/ws/fact-check/${sessionId}/`);
```

## 🏗️ System Architecture

```
User Input → Django API → Celery Task → ChatGPT Analysis
                                    ↓
WebSocket Updates ← Real-time Progress ← Multi-step Process:
                                         1. Topic Analysis
                                         2. Source Search
                                         3. Content Extraction
                                         4. Source Evaluation
                                         5. Final Verdict
```

## 🔧 Configuration Files

- `factcheck_backend/settings.py` - Main Django config
- `factcheck_backend/celery.py` - Celery configuration
- `apps/api/views.py` - API endpoints
- `apps/fact_checker/services/` - Core services
- `requirements.txt` - Python dependencies

## 🚨 Troubleshooting

**Redis Connection Issues:**
```bash
# Check if Redis is running
redis-cli ping
# Should return "PONG"
```

**API Key Issues:**
- Verify OpenAI API key has sufficient credits
- Check Google Custom Search API is enabled
- Ensure search engine ID is correct

**Celery Worker Issues:**
```bash
# Check worker status
celery -A factcheck_backend inspect active
```

## 📊 Monitoring

**Check System Health:**
```bash
curl http://localhost:8000/api/health/
```

**Monitor Celery Tasks:**
```bash
# Install flower for web monitoring
pip install flower
celery -A factcheck_backend flower
# Visit http://localhost:5555
```

## 🔐 Production Checklist

- [ ] Set `DEBUG=False`
- [ ] Configure PostgreSQL database
- [ ] Set up proper Redis instance
- [ ] Configure SSL/HTTPS
- [ ] Set up rate limiting
- [ ] Configure proper logging
- [ ] Set up monitoring
- [ ] Configure CORS for your domain

## 🎯 Next Steps

1. **Frontend Integration**: Connect with your Vue.js application
2. **Authentication**: Add user authentication if needed
3. **Rate Limiting**: Implement API rate limiting
4. **Caching**: Add Redis caching for repeated queries
5. **Monitoring**: Set up application monitoring
6. **Testing**: Add comprehensive unit tests

## 💡 Tips

- Monitor API usage to control costs
- Implement caching for repeated fact-checks
- Consider implementing user accounts for tracking
- Add analytics to understand usage patterns
- Regular database cleanup of old sessions

---

Your fact-checking backend is now ready! 🎉

The system provides:
✅ Multi-step AI-powered analysis
✅ Real-time progress updates
✅ Comprehensive source evaluation
✅ RESTful API
✅ WebSocket support
✅ Asynchronous processing
✅ Production-ready architecture
