# MBTI Chat

A conversational MBTI personality assessment app that analyzes your personality type through natural conversation.
<img src="![Image](https://github.com/user-attachments/assets/b925009e-1eec-40ab-9754-3210fb9eebb7)">
## Overview

MBTI Chat is an innovative application that uses natural language processing to determine a user's Myers-Briggs Type Indicator (MBTI) personality type through casual conversation. Unlike traditional MBTI assessments that use explicit multiple-choice questions, this app engages users in a natural dialogue and analyzes their responses to identify personality traits.

## Features

- **Conversational Assessment**: Determines personality type through natural conversation rather than explicit questions
- **Dynamic Questioning**: Adjusts follow-up questions based on previous responses
- **Real-time Analysis**: Provides real-time confidence scoring for each MBTI dimension
- **Comprehensive Results**: Displays detailed personality type information when assessment is complete
- **Responsive UI**: Clean, intuitive interface that works on both desktop and mobile devices
- **Korean Language Support**: Fully supports Korean language for the interface and conversational analysis

## Technical Stack

- **Backend**: Python/Flask with SQLAlchemy
- **Frontend**: HTML, CSS, JavaScript, Bootstrap
- **Database**: PostgreSQL
- **AI**: OpenAI GPT-4o API for natural language understanding and conversation generation
- **ORM**: Flask-SQLAlchemy for database interaction

## How It Works

1. The system engages the user in natural conversation
2. Each user response is analyzed for MBTI-relevant traits (E/I, S/N, T/F, J/P)
3. The system asks thoughtful follow-up questions that target dimensions with lower confidence scores
4. After exactly 5 messages, the system provides a complete MBTI assessment
5. Results include the four-letter type, description, and confidence levels for each dimension

## Requirements

- Python 3.11+
- PostgreSQL database
- OpenAI API key
- Flask and related dependencies (see requirements.txt)

## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up environment variables:
   - `DATABASE_URL`: PostgreSQL database URL
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `SESSION_SECRET`: Secret key for Flask session
4. Run the application: `python main.py`


## Acknowledgments

- Myers-Briggs Type Indicator (MBTI) framework
- OpenAI GPT models for natural language processing
