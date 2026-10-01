# Steam Skills Profile

A tool to generate a beautiful, personalized infographic of your Steam gaming profile and skills based on your owned games and playtime.

## Overview
This project fetches data from the Steam Web API to analyze your game library and categorize your playstyle. It generates a summary chart highlighting the genres and tags you play the most, creating a customized "gamer profile".

## Features
- Fetches and caches game data using the Steam Web API
- Categorizes games into skills/genres
- Generates a visual infographic (PNG) or JSON export
- Runs locally or can be deployed as an API

## Getting Started

1. Get a [Steam Web API Key](https://steamcommunity.com/dev/apikey)
2. Add your API key to a `.env` file (see `.env.example` for reference)
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the local server:
   ```bash
   python serve.py
   ```
5. Open your browser and navigate to the provided local URL to generate your profile.

## License
MIT License
