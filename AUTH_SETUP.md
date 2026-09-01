# Tessera Authentication Setup Guide

## Overview
Tessera now uses email/password authentication instead of bearer tokens. Users create accounts, log in, and can query without limits.

---

## Files Changed/Added

### New Files
- **auth.py** - SQLite authentication module
  - Database: `tessera_users.db` (auto-created)
  - Handles: user registration, login, password hashing, query logging
  
- **app_streamlit_auth.py** - New authenticated Streamlit frontend
  - Login/signup page
  - User session management
  - Blue/brown color theme
  - Query history with statistics

### Replaced Files
- **app_streamlit.py** → **app_streamlit_auth.py**
  - Old token-based auth removed
  - New email/password flow
  - Better UI colors
  - User stats tracking

---

## Setup Instructions

### 1. Install Dependencies
```bash
pip install streamlit requests pypdf sqlite3
```

### 2. File Structure
```
AI-JOB-Search-Project-2/
├── auth.py                    # New: Authentication module
├── app_streamlit_auth.py      # New: Authenticated Streamlit app
├── app_streamlit.py           # Old: Token-based app (keep as backup)
├── tessera_users.db           # Auto-created by auth.py
└── src/
    ├── api/
    │   └── app.py             # FastAPI backend (unchanged)
    ├── rag/
    │   └── agent_pipeline.py  # RAG logic (unchanged)
    └── ...
```

### 3. Run the App
```bash
# Start the backend API first
cd src/api
uvicorn app:app --host 0.0.0.0 --port 8000

# In another terminal, start Streamlit with auth
streamlit run app_streamlit_auth.py
```

### 4. First Time Users
- Go to **Sign Up** section (left column)
- Enter email, password (min 6 chars), confirm password
- Click "Create Account"
- Switch to **Login** (right column)
- Enter same email and password
- Click "Login"

---

## Database Schema

### Users Table
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
)
```

### User Queries Table
```sql
CREATE TABLE user_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    answer TEXT,
    route TEXT,
    tokens_used INTEGER,
    cost_usd REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
)
```

### User Sessions Table
```sql
CREATE TABLE user_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_token TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
)
```

---

## Features

### Authentication
✅ Email/password signup
✅ Secure login with password hashing (SHA-256)
✅ User session tracking
✅ Last login timestamp
✅ Account isolation

### User Experience
✅ Blue/brown color theme (readable, professional)
✅ User email displayed in sidebar
✅ Logout button
✅ Query history preserved in session
✅ User statistics dashboard

### Query Tracking
✅ Every question logged with:
  - Question text
  - Answer text
  - Route used (vector/web/direct)
  - Tokens consumed
  - Estimated cost
  - Timestamp

✅ User statistics:
  - Total queries
  - Total tokens used
  - Total cost (USD)

### Retrieval Options (Unchanged from before)
✅ Retriever type: vector or direct
✅ Web search toggle
✅ Top-K adjustment (1-20)
✅ Self-checking toggle
✅ Execution trace option

### File Upload
✅ Support for .pdf, .md, .txt
✅ Auto PDF text extraction
✅ Per-user document isolation

---

## Configuration

### In the UI Sidebar

**Connection Settings**
- API Base URL: `http://localhost:8000` (default)
- Bearer Token: Your token for the API (if needed)
- Health Check: Verify API connection

**Retrieval Configuration**
- Retriever Type: Choose "vector" or "direct"

**Search Options**
- Enable web search: Checkbox

**Generation Settings**
- Top-K: Slider 1-20 (default 5)

**Advanced Settings**
- Self-checking: Toggle (default ON)
- Show execution trace: Toggle (default OFF)

**User Statistics**
- Shows your personal query stats
- Total queries, tokens, cost

---

## API Integration

### Backend Still Uses Bearer Tokens
The FastAPI backend still expects bearer tokens for multi-tenancy.
The Streamlit app uses bearer tokens to communicate with the API.

### Flow
```
User (Email/Password)
    ↓
Streamlit Auth (Validates locally)
    ↓
Bearer Token → API Request
    ↓
FastAPI (Validates token)
    ↓
Response → Tessera
    ↓
Query Logged → SQLite
```

---

## Security Notes

### Password Storage
- Passwords hashed with SHA-256
- Never stored in plain text
- Hashes stored in SQLite

### Session Management
- User ID kept in Streamlit session state
- User email displayed in sidebar
- Logout clears session

### Data Isolation
- Each user's queries logged separately
- No cross-user data access
- SQLite database file: `tessera_users.db`

### Multi-Tenancy (Backend)
- Bearer tokens still control backend tenancy
- User authentication is separate layer
- One user can belong to multiple tenants (via different tokens)

---

## Troubleshooting

### "Password must be at least 6 characters"
✓ Enter a password with 6+ characters

### "User already exists"
✓ Try logging in instead of signing up
✓ Use forgot password (not implemented yet)

### "Invalid email or password"
✓ Check email spelling
✓ Check password exactly
✓ Note: Passwords are case-sensitive

### 401 Unauthorized from API
✓ Check your bearer token in sidebar
✓ Verify API is running on correct port
✓ Try health check button

### "Connection failed: could not reach the API"
✓ Start the FastAPI backend first
✓ Check API_BASE URL is correct
✓ Verify port 8000 is not in use

---

## Migration from Token-Based App

If you were using `app_streamlit.py`:

1. **Backup old app**
   ```bash
   cp app_streamlit.py app_streamlit.py.backup
   ```

2. **Use new auth app**
   ```bash
   streamlit run app_streamlit_auth.py
   ```

3. **Create account**
   - Sign up with your email/password
   - Log in
   - Continue using normally

4. **Old data**
   - Previous queries (in memory) are lost
   - Uploaded documents remain in backend API
   - New queries are logged to SQLite

---

## Future Enhancements

Planned improvements:
- [ ] Forgot password flow
- [ ] Email verification
- [ ] User profiles
- [ ] Query history export
- [ ] Persistent chat history (save to database)
- [ ] Multiple tenants per user
- [ ] Admin dashboard
- [ ] Rate limiting per user
- [ ] API key management
- [ ] PostgreSQL option (replace SQLite)

---

## Testing

### Test User
```
Email: test@tessera.dev
Password: test123456
```

### Manual Test Steps
1. Sign up with new email
2. Log in
3. Set API base URL
4. Add bearer token
5. Upload a document
6. Ask a question
7. Check sidebar for stats
8. Logout and login again
9. Verify query history preserved

---

## Database Inspection

### View Users
```bash
sqlite3 tessera_users.db
SELECT * FROM users;
```

### View User Queries
```bash
SELECT * FROM user_queries WHERE user_id = 1;
```

### View Statistics
```bash
SELECT user_id, COUNT(*) as queries, SUM(tokens_used) as total_tokens, SUM(cost_usd) as total_cost
FROM user_queries
GROUP BY user_id;
```

### Reset Database (if needed)
```bash
rm tessera_users.db
# Recreate by running app again
```

---

## Support

For issues:
1. Check troubleshooting section above
2. Enable "Show execution trace" for debugging
3. Check API health status
4. Verify bearer token is correct
5. Check API logs for errors

