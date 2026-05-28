# The Punting Lab - Horse Racing Overlay

A comprehensive horse racing analysis and overlay system with web scraping, data analysis, and visualization capabilities.

## Project Structure

```
├── backend/
│   └── backend-new/          # Main backend application
│       ├── main.py           # Entry point
│       ├── scraper.py        # Web scraping logic
│       ├── agents.py         # Agent-based analysis
│       ├── database.py       # Database operations
│       ├── overlay_model.py  # Overlay data model
│       ├── weather.py        # Weather data integration
│       └── requirements.txt  # Python dependencies
└── README.md
```

## Quick Start

### Prerequisites
- Python 3.8+
- Git

### Installation

1. Clone the repository:
```bash
git clone https://github.com/jordymacc/The-Punting-Lab.git
cd The-Punting-Lab
```

2. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
cd backend/backend-new
pip install -r requirements.txt
```

### Running the Application

```bash
python main.py
```

## Features

- **Web Scraping**: Automated scraping of horse racing data from multiple sources
- **Data Analysis**: Agent-based analysis system for race predictions
- **Weather Integration**: Real-time weather data for race conditions
- **Database**: SQLite database for storing historical data
- **Overlay Model**: Data visualization and overlay capabilities

## Development

### Project Dependencies

See `backend/backend-new/requirements.txt` for all dependencies.

### Database

The application uses SQLite (`racing.db`) to store historical race data.

## Contributing

1. Create a new branch for your feature
2. Make your changes
3. Test thoroughly
4. Submit a pull request

## License

[Add your license here]

## Author

Jordan Macc
