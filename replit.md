# Overview

This repository contains a comprehensive Arabic Telegram bot for Pixabay content search with mandatory subscription verification and full admin management features. The bot is built with Python using the python-telegram-bot library and includes search functionality for various media types (photos, videos, vectors, illustrations, music, GIFs), user management, and statistics tracking.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Core Framework
- **Python-based Telegram Bot**: Built using the `python-telegram-bot` library for handling Telegram API interactions
- **Asynchronous Architecture**: Uses Python's `asyncio` for handling concurrent operations
- **SQLite Database**: Local file-based database for data persistence
- **REST API Integration**: External service calls to Pixabay API for image searching

## Application Structure
The application follows a single-file architecture pattern with modular function organization:
- Main application logic in `main.py`
- Database initialization and management functions
- Bot command handlers and callback processors
- External API integration utilities

# Key Components

## Database Layer
- **SQLite Database**: File-based storage (`bot_data.db`)
- **Users Table**: Stores user registration and profile information
- **Connection Management**: Direct SQLite3 connections with proper cursor handling

## Bot Interface
- **Command Handlers**: Process user commands (likely `/start`, `/help`, etc.)
- **Callback Query Handlers**: Handle inline keyboard interactions
- **Message Handlers**: Process text and media messages
- **Inline Keyboards**: Interactive button-based user interface

## External Services
- **Pixabay Integration**: Image search and retrieval functionality
- **Telegram Bot API**: Core messaging and user interaction platform

## Authentication & Authorization
- **Admin System**: Single admin user identified by `ADMIN_ID`
- **User Management**: User registration and tracking system
- **Role-based Access**: Admin-specific functionalities

# Data Flow

## User Interaction Flow
1. Users interact with bot through Telegram interface
2. Bot processes commands/messages through appropriate handlers
3. User data is stored/retrieved from SQLite database
4. External API calls made when image search is requested
5. Responses sent back to users through Telegram API

## Data Persistence
- User information stored in SQLite database
- Session data managed through bot context
- Configuration loaded from environment variables

# External Dependencies

## Core Libraries
- `python-telegram-bot`: Telegram Bot API wrapper
- `sqlite3`: Database connectivity (Python standard library)
- `requests`: HTTP client for external API calls
- `asyncio`: Asynchronous programming support

## External Services
- **Telegram Bot API**: Primary platform for bot operations
- **Pixabay API**: Image search and retrieval service

## Environment Configuration
- `BOT_TOKEN`: Telegram bot authentication token
- `ADMIN_ID`: Administrator user identifier
- `PIXABAY_API_KEY`: Pixabay service API key

# Deployment Strategy

## Local Development
- Single Python file execution
- Environment variables for configuration
- Local SQLite database file
- Direct bot token authentication

## Production Considerations
- Environment-based configuration management
- Database file persistence requirements
- Bot token security
- API rate limiting considerations

## Dependencies Management
- Standard Python package management
- External API key configuration
- Telegram webhook or polling setup requirements

The architecture prioritizes simplicity and direct functionality, making it suitable for small to medium-scale bot operations with straightforward deployment requirements.