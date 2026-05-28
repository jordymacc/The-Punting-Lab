# The Punting Lab - Frontend

A horse racing overlay dashboard that connects to the live backend API to display real-time race data, overlays, and analysis.

**🌐 Live Backend:** https://punting-lab-backend.onrender.com/

## Project Structure

```
frontend/
├── index.html      # Main dashboard page
├── bulk.html       # Bulk race view
├── app.js          # Main JavaScript application
└── style.css       # Stylesheet
```

## Features

- 🏇 Real-time horse racing overlay dashboard
- 🔴 Live WebSocket connection for instant updates
- 📊 Race cards with overlay ratings and analysis
- 🔍 Filter by rating, track and sort options
- ⏱️ Live race countdown timers
- 📈 Race results tracking and history
- 🟢 Live connection status indicator

## Tech Stack

- **HTML5** - Structure and layout
- **CSS3** - Styling and responsive design
- **Vanilla JavaScript** - Application logic
- **WebSocket** - Real-time data updates
- **REST API** - Data fetching from backend

## Quick Start

### Option 1: Open Directly
Simply open `index.html` in your browser.

### Option 2: Use Live Server (Recommended)
1. Install VS Code Live Server extension
2. Right-click `index.html`
3. Click 'Open with Live Server'

## API Connection

The frontend connects to the backend via:

- **REST API:** https://punting-lab-backend.onrender.com
- **WebSocket:** ws://localhost:8000/ws (local development)

To change the API endpoint, update the following line in `app.js`:
```javascript
const API = 'https://punting-lab-backend.onrender.com';
```

## Dashboard Features

### Filters
- **Rating Filter** - Filter races by overlay rating
- **Track Filter** - Filter by specific race track
- **Sort Options** - Sort races by different criteria

### Status Indicator
- 🟢 Green - Live and connected
- 🔴 Red - Connection lost
- ⚫ Grey - Connecting...

### Auto Refresh
- Data automatically refreshes every 60 seconds
- WebSocket provides instant updates when available

## Development

### Prerequisites
- Modern web browser (Chrome, Firefox, Edge)
- Backend running locally or using the live Render URL

### Running Locally with Backend
1. Start the backend:
```bash
cd backend/backend-new
python main.py
```
2. Open `frontend/index.html` in your browser

## Author

Jordan Macc

---

**Status:** 🟢 Backend Live | 🟡 Frontend In Development
