import os
import logging
import json
from flask import Flask, render_template, request, jsonify, session
from mbti_analyzer import MBTIAnalyzer

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")

# Initialize MBTI analyzer
mbti_analyzer = MBTIAnalyzer()

@app.route('/')
def index():
    """Render the main chat interface."""
    # Initialize or reset the session conversation history
    session['conversation'] = []
    session['assessment_state'] = {
        'E_I': {'score': 0, 'confidence': 0},
        'S_N': {'score': 0, 'confidence': 0},
        'T_F': {'score': 0, 'confidence': 0},
        'J_P': {'score': 0, 'confidence': 0}
    }
    session['assessment_complete'] = False
    
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    """Process user message and return AI response."""
    try:
        # Get user message from request
        data = request.get_json()
        user_message = data.get('message', '')
        
        # Retrieve conversation history and assessment state from session
        conversation = session.get('conversation', [])
        assessment_state = session.get('assessment_state', {
            'E_I': {'score': 0, 'confidence': 0},
            'S_N': {'score': 0, 'confidence': 0},
            'T_F': {'score': 0, 'confidence': 0},
            'J_P': {'score': 0, 'confidence': 0}
        })
        assessment_complete = session.get('assessment_complete', False)
        
        # Add user message to conversation history
        conversation.append({"role": "user", "content": user_message})
        
        # Process message through MBTI analyzer
        response, updated_assessment_state, assessment_complete = mbti_analyzer.process_message(
            user_message, 
            conversation,
            assessment_state,
            assessment_complete
        )
        
        # Add AI response to conversation history
        conversation.append({"role": "assistant", "content": response})
        
        # Update session
        session['conversation'] = conversation
        session['assessment_state'] = updated_assessment_state
        session['assessment_complete'] = assessment_complete
        
        # Prepare response
        result = {
            "response": response,
            "assessment_state": updated_assessment_state,
            "assessment_complete": assessment_complete
        }
        
        if assessment_complete:
            # Calculate MBTI type when assessment is complete
            mbti_type = mbti_analyzer.calculate_mbti_type(updated_assessment_state)
            mbti_description = mbti_analyzer.get_mbti_description(mbti_type)
            result["mbti_type"] = mbti_type
            result["mbti_description"] = mbti_description
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/reset', methods=['POST'])
def reset():
    """Reset the conversation and assessment state."""
    session['conversation'] = []
    session['assessment_state'] = {
        'E_I': {'score': 0, 'confidence': 0},
        'S_N': {'score': 0, 'confidence': 0},
        'T_F': {'score': 0, 'confidence': 0},
        'J_P': {'score': 0, 'confidence': 0}
    }
    session['assessment_complete'] = False
    
    return jsonify({"status": "success", "message": "Conversation reset"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
