import os
import json
import logging
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class MBTIAnalyzer:
    def __init__(self):
        """Initialize the MBTI analyzer with OpenAI client."""
        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        # do not change this unless explicitly requested by the user
        self.model = "gpt-4o"
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.openai_api_key)
        self.confidence_threshold = 0.8  # Threshold to determine when assessment is complete - higher value requires longer conversations

    def process_message(self, user_message, conversation, assessment_state, assessment_complete, message_count=0, min_messages_needed=10, last_focus_dimension=None):
        """
        Process user message and update MBTI assessment state.
        
        Args:
            user_message (str): The user's message
            conversation (list): Conversation history
            assessment_state (dict): Current MBTI assessment scores and confidence
            assessment_complete (bool): Whether assessment is complete
            message_count (int): Current number of user messages
            min_messages_needed (int): Minimum number of user messages required for assessment
            last_focus_dimension (str): The dimension that was focused on in the previous message
            
        Returns:
            tuple: (AI response, updated assessment state, assessment complete flag, last focused dimension)
        """
        try:
            # If assessment is already complete, just have a normal conversation
            if assessment_complete:
                response, next_focus = self._generate_response(
                    user_message, 
                    conversation, 
                    assessment_state, 
                    True,
                    message_count,
                    min_messages_needed,
                    last_focus_dimension
                )
                return response, assessment_state, assessment_complete, next_focus
            
            # Analyze the message for MBTI traits and get updated assessment
            updated_assessment = self._analyze_mbti_traits(user_message, conversation, assessment_state)
            
            # Check if assessment is complete based on confidence levels and message count
            is_complete = self._check_assessment_complete(
                updated_assessment,
                message_count,
                min_messages_needed
            )
            
            # Generate appropriate response based on assessment state
            response, new_focus_dimension = self._generate_response(
                user_message, 
                conversation, 
                updated_assessment, 
                is_complete,
                message_count,
                min_messages_needed,
                last_focus_dimension
            )
            
            return response, updated_assessment, is_complete, new_focus_dimension
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return "I'm having trouble processing your message. Could you try again?", assessment_state, assessment_complete, None

    def _analyze_mbti_traits(self, user_message, conversation, current_assessment):
        """
        Analyze user message to update MBTI trait scores and confidence.
        
        Args:
            user_message (str): The user's message
            conversation (list): Conversation history
            current_assessment (dict): Current MBTI assessment state
            
        Returns:
            dict: Updated assessment state
        """
        # Prepare conversation context for analysis
        context = []
        for message in conversation[-8:]:  # Use last 8 messages for context to provide more history
            context.append({"role": message["role"], "content": message["content"]})
        
        # Define the analysis prompt
        system_prompt = """
        You are an expert MBTI personality analyst. Your task is to analyze the user's messages to determine
        their MBTI type based on the following dimensions:
        
        E vs I: Extraversion vs Introversion - how the person gets their energy and interacts with others
        S vs N: Sensing vs Intuition - how the person processes information
        T vs F: Thinking vs Feeling - how the person makes decisions
        J vs P: Judging vs Perceiving - how the person approaches structure and planning
        
        Based on the user's message, analyze each dimension and provide:
        1. A score from -1.0 to 1.0 where:
           - For E/I: -1.0 means strongly Introverted, 1.0 means strongly Extraverted
           - For S/N: -1.0 means strongly Sensing, 1.0 means strongly Intuitive
           - For T/F: -1.0 means strongly Thinking, 1.0 means strongly Feeling
           - For J/P: -1.0 means strongly Judging, 1.0 means strongly Perceiving
        
        2. A confidence value from 0.0 to 1.0 indicating how certain you are about this assessment
        
        Respond with JSON only in this exact format:
        {
            "E_I": {"score": float, "confidence": float, "reasoning": "brief explanation"},
            "S_N": {"score": float, "confidence": float, "reasoning": "brief explanation"},
            "T_F": {"score": float, "confidence": float, "reasoning": "brief explanation"},
            "J_P": {"score": float, "confidence": float, "reasoning": "brief explanation"}
        }
        """
        
        try:
            # Call OpenAI API to analyze the message
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    *context,
                    {"role": "user", "content": f"Analyze this message: {user_message}"}
                ],
                response_format={"type": "json_object"}
            )
            
            # Parse the response
            analysis = json.loads(response.choices[0].message.content)
            
            # Update assessment state with weighted average of current and new analysis
            updated_assessment = current_assessment.copy()
            
            for dimension in ['E_I', 'S_N', 'T_F', 'J_P']:
                current = current_assessment[dimension]
                new = analysis[dimension]
                
                # Skip if confidence is very low in new analysis
                if new['confidence'] < 0.2:
                    continue
                
                # Calculate weighted average based on confidence
                if current['confidence'] == 0:
                    # First assessment for this dimension
                    updated_assessment[dimension] = {
                        'score': new['score'],
                        'confidence': new['confidence']
                    }
                else:
                    # Combine with existing assessment
                    total_confidence = current['confidence'] + new['confidence']
                    weighted_score = (
                        (current['score'] * current['confidence']) + 
                        (new['score'] * new['confidence'])
                    ) / total_confidence
                    
                    # Increase confidence, but at a slower rate and don't exceed 0.95
                    # Use a smaller factor (0.6 instead of 0.8) and cap at 0.95 to always allow for more questions
                    new_confidence = min(current['confidence'] + (new['confidence'] * 0.3), 0.95)
                    
                    updated_assessment[dimension] = {
                        'score': weighted_score,
                        'confidence': new_confidence
                    }
            
            return updated_assessment
            
        except Exception as e:
            logger.error(f"Error analyzing MBTI traits: {str(e)}")
            # Return original assessment if analysis fails
            return current_assessment

    def _check_assessment_complete(self, assessment, message_count=0, min_messages_needed=10):
        """
        Check if MBTI assessment is complete based on confidence thresholds and
        minimum number of messages.
        
        Args:
            assessment (dict): Current MBTI assessment state
            message_count (int): Current number of user messages
            min_messages_needed (int): Minimum number of user messages required
            
        Returns:
            bool: True if assessment is complete, False otherwise
        """
        # Check if minimum message count is reached
        if message_count < min_messages_needed:
            return False
            
        # Check if all dimensions have confidence above threshold
        for dimension, values in assessment.items():
            if values['confidence'] < self.confidence_threshold:
                return False
        
        return True

    def _generate_response(self, user_message, conversation, assessment, is_complete, message_count=0, min_messages_needed=10, last_focus_dimension=None):
        """
        Generate appropriate response based on assessment state.
        
        Args:
            user_message (str): The user's message
            conversation (list): Conversation history
            assessment (dict): Current MBTI assessment state
            is_complete (bool): Whether assessment is complete
            message_count (int): Current number of user messages
            min_messages_needed (int): Minimum number of user messages required
            last_focus_dimension (str): The dimension that was focused on in the previous message
            
        Returns:
            tuple: (AI response, next dimension to focus on)
        """
        # Prepare conversation context
        context = []
        for message in conversation[-8:]:  # Use last 8 messages for context
            context.append({"role": message["role"], "content": message["content"]})
        
        # Define the system prompt based on assessment state
        next_focus_dimension = None  # Initialize the return value
        
        if is_complete:
            mbti_type = self.calculate_mbti_type(assessment)
            
            # Generate reasoning for each dimension
            e_i_reason = "외향적" if assessment['E_I']['score'] > 0 else "내향적"
            s_n_reason = "감각적" if assessment['S_N']['score'] < 0 else "직관적"
            t_f_reason = "사고적" if assessment['T_F']['score'] < 0 else "감정적"
            j_p_reason = "판단적" if assessment['J_P']['score'] < 0 else "인식적"
            
            system_prompt = f"""
            You are a friendly personality assessment chatbot. The user's MBTI assessment is now complete, 
            and they appear to be a {mbti_type} personality type.
            
            The assessment shows they are:
            - {e_i_reason} (점수: {abs(assessment['E_I']['score']):.2f}, 확신도: {assessment['E_I']['confidence']:.2f})
            - {s_n_reason} (점수: {abs(assessment['S_N']['score']):.2f}, 확신도: {assessment['S_N']['confidence']:.2f})
            - {t_f_reason} (점수: {abs(assessment['T_F']['score']):.2f}, 확신도: {assessment['T_F']['confidence']:.2f})
            - {j_p_reason} (점수: {abs(assessment['J_P']['score']):.2f}, 확신도: {assessment['J_P']['confidence']:.2f})
            
            When the user asks about their results, share their MBTI type ({mbti_type}) and explain the reasoning
            behind each dimension, including specific examples from the conversation that led to this assessment.
            
            Be warm, personable, and avoid any stilted or clinical tone. Talk like a supportive friend.
            """
        else:
            # Calculate dimensions that need more assessment
            low_confidence_dimensions = []
            for dimension, values in assessment.items():
                if values['confidence'] < self.confidence_threshold:
                    low_confidence_dimensions.append(dimension)
            
            # Suggest specific target questions based on dimensions that need assessment
            target_questions = {
                'E_I': [
                    "주말에 어떻게 시간을 보내는 것을 좋아하시나요?",
                    "많은 사람들과 함께 있을 때와 혼자 있을 때 어떤 기분이 드나요?",
                    "새로운 사람들을 만나는 자리에서 어떤 느낌이 드나요?",
                    "에너지를 얻는 방법에 대해 이야기해 주실 수 있나요?"
                ],
                'S_N': [
                    "미래에 대해 계획을 세울 때 어떤 방식으로 접근하시나요?",
                    "문제를 해결할 때 주로 어떤 접근 방식을 사용하시나요?",
                    "새로운 아이디어나 개념을 접할 때 어떤 면에 더 집중하시나요?",
                    "정보를 기억하고 처리하는 데 어떤 방식이 가장 편하신가요?"
                ],
                'T_F': [
                    "어려운 결정을 내릴 때 주로 어떤 요소를 고려하시나요?",
                    "다른 사람과 의견 충돌이 있을 때 어떻게 대처하시나요?",
                    "다른 사람에게 피드백을 줄 때 어떤 접근 방식을 선호하시나요?",
                    "타인의 감정을 다루는 상황에서 어떤 경험이 있으신가요?"
                ],
                'J_P': [
                    "일상에서 계획을 세우는 편인가요, 즉흥적으로 행동하는 편인가요?",
                    "업무나 과제를 진행할 때 어떤 방식으로 접근하시나요?",
                    "마감 기한이 있는 일을 처리할 때는 보통 어떻게 하시나요?",
                    "예상치 못한 변화가 생길 때 어떻게 대응하시나요?"
                ]
            }
            
            # Find a dimension to focus on based on a rotation strategy and confidence levels
            # Use a rotation strategy with weighting towards dimensions with lower confidence
            
            # Use the previous focus dimension that was passed in
            prev_focus = last_focus_dimension
            
            # Create a weighted list based on inverse confidence
            dimension_weights = {}
            for dim, values in assessment.items():
                # Higher weight for lower confidence
                # Avoid division by zero by adding a small constant
                weight = 1.0 / (values['confidence'] + 0.1)
                
                # Give lower weight to the previously focused dimension to encourage rotation
                if dim == prev_focus:
                    weight *= 0.5
                    
                dimension_weights[dim] = weight
            
            # Sort by weight (highest weight first)
            sorted_dimensions = sorted(dimension_weights.items(), key=lambda x: x[1], reverse=True)
            focus_dimension = sorted_dimensions[0][0]  # Get the dimension with highest weight
            
            # Store the focus dimension for tracking and return it in the API
            next_focus_dimension = focus_dimension
            
            system_prompt = f"""
            You are a friendly personality assessment chatbot having a natural conversation to determine 
            the user's MBTI personality type. Your goal is to ask questions and engage in dialogue that helps
            reveal their personality traits.
            
            Current assessment state:
            E/I: Score {assessment['E_I']['score']:.2f}, Confidence {assessment['E_I']['confidence']:.2f}
            S/N: Score {assessment['S_N']['score']:.2f}, Confidence {assessment['S_N']['confidence']:.2f}
            T/F: Score {assessment['T_F']['score']:.2f}, Confidence {assessment['T_F']['confidence']:.2f}
            J/P: Score {assessment['J_P']['score']:.2f}, Confidence {assessment['J_P']['confidence']:.2f}
            
            Message count: {message_count} of {min_messages_needed} required messages
            Dimensions that need more assessment: {", ".join(low_confidence_dimensions)}
            
            The dimension with the lowest confidence is: {focus_dimension}
            
            Here are some target questions you can use to assess this dimension:
            {target_questions[focus_dimension]}
            
            Guidelines:
            1. Maintain a casual, friendly conversation - don't make it obvious you're assessing them
            2. Ask SPECIFIC open-ended questions that might reveal personality traits, especially for dimensions with low confidence
            3. Avoid directly asking about MBTI or explaining that you're assessing them
            4. If they ask what you're doing, be honest but gentle about the personality assessment
            5. Keep responses conversational and not overly long
            6. Respond to the user's message directly, then guide the conversation with ONE specific question
            
            Keep the conversation flowing naturally as if you're just chatting with a friend, but be strategic about getting information about their personality traits.
            """
        
        try:
            # Call OpenAI API to generate response
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    *context
                ]
            )
            
            return response.choices[0].message.content, next_focus_dimension
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return "I'm having trouble generating a response. Let's continue our conversation. How are you feeling today?", None

    def calculate_mbti_type(self, assessment):
        """
        Calculate the MBTI type based on assessment scores.
        
        Args:
            assessment (dict): MBTI assessment state
            
        Returns:
            str: MBTI type (e.g., "INTJ")
        """
        mbti_type = ""
        
        # E vs I
        mbti_type += "E" if assessment['E_I']['score'] > 0 else "I"
        
        # S vs N
        mbti_type += "S" if assessment['S_N']['score'] < 0 else "N"
        
        # T vs F
        mbti_type += "T" if assessment['T_F']['score'] < 0 else "F"
        
        # J vs P
        mbti_type += "J" if assessment['J_P']['score'] < 0 else "P"
        
        return mbti_type

    def get_mbti_description(self, mbti_type):
        """
        Get description for MBTI type.
        
        Args:
            mbti_type (str): MBTI type (e.g., "INTJ")
            
        Returns:
            dict: Description and details for the MBTI type
        """
        # Define descriptions for each MBTI type
        descriptions = {
            "INTJ": {
                "title": "The Architect",
                "description": "INTJs are strategic, innovative thinkers with a talent for logical analysis and long-term planning. They're driven by their own original ideas and often work best independently.",
                "strengths": "Strategic thinking, independence, rational analysis, determination",
                "weaknesses": "Can be overly critical, dismissive of emotions, perfectionistic"
            },
            "INTP": {
                "title": "The Logician",
                "description": "INTPs are innovative inventors with an unquenchable thirst for knowledge. They love theoretical and abstract concepts and excel at finding logical inconsistencies.",
                "strengths": "Analytical thinking, creativity, objectivity, openness to new ideas",
                "weaknesses": "Can be absent-minded, insensitive, perfectionist, or socially detached"
            },
            "ENTJ": {
                "title": "The Commander",
                "description": "ENTJs are bold, imaginative leaders who have a knack for finding intelligent solutions to difficult problems. They're strategic planners who often take charge naturally.",
                "strengths": "Efficient, energetic, self-confident, strong-willed, strategic",
                "weaknesses": "Can be impatient, stubborn, arrogant, or insensitive to others' feelings"
            },
            "ENTP": {
                "title": "The Debater",
                "description": "ENTPs are smart, curious thinkers who enjoy intellectual challenges and can't resist a good debate. They're creative problem solvers who see connections others might miss.",
                "strengths": "Knowledgeable, creative, excellent brainstorming, energetic",
                "weaknesses": "May argue for fun, dislike practical matters, procrastinate"
            },
            "INFJ": {
                "title": "The Advocate",
                "description": "INFJs are insightful, creative idealists motivated by deep convictions and a desire to help others. They seek meaning in relationships and work to understand others' perspectives.",
                "strengths": "Creative, insightful, principled, passionate, altruistic",
                "weaknesses": "Can be sensitive to criticism, perfectionistic, private, or burn out easily"
            },
            "INFP": {
                "title": "The Mediator",
                "description": "INFPs are imaginative idealists guided by their core values and beliefs. They're curious, creative, and adaptable, with a strong desire to live a life that aligns with their values.",
                "strengths": "Empathetic, creative, passionate, idealistic, dedicated to values",
                "weaknesses": "May be unrealistic, overly idealistic, too self-critical, or impractical"
            },
            "ENFJ": {
                "title": "The Protagonist",
                "description": "ENFJs are charismatic leaders who naturally understand and connect with others. They're often focused on helping others develop and fulfill their potential.",
                "strengths": "Warm, empathetic, reliable, natural leaders, compelling communicators",
                "weaknesses": "Can be too selfless, overly idealistic, too sensitive to criticism"
            },
            "ENFP": {
                "title": "The Campaigner",
                "description": "ENFPs are enthusiastic, creative free spirits who find potential and possibility everywhere. They're excellent at connecting with others and bringing energy to situations.",
                "strengths": "Enthusiastic, creative, people-oriented, energetic, empathetic",
                "weaknesses": "Can be overly emotional, disorganized, overthink, or struggle with follow-through"
            },
            "ISTJ": {
                "title": "The Logistician",
                "description": "ISTJs are practical, fact-minded individuals with an unwavering respect for facts and a dedication to reliability. They value traditions and loyalty.",
                "strengths": "Honest, direct, dependable, organized, practical and responsible",
                "weaknesses": "May be stubborn, insensitive, or resistant to change and new ideas"
            },
            "ISFJ": {
                "title": "The Defender",
                "description": "ISFJs are protective, devoted individuals who enjoy contributing to established structures and traditions. They're practical helpers with excellent attention to detail.",
                "strengths": "Supportive, reliable, observant, enthusiastic, loyal, detail-oriented",
                "weaknesses": "Can be overworked, reluctant to change, overly humble, take criticism personally"
            },
            "ESTJ": {
                "title": "The Executive",
                "description": "ESTJs are excellent administrators who like to take charge and manage people and situations. They value order, structure, and clear communication.",
                "strengths": "Dedicated, strong-willed, practical, direct, honest, loyal",
                "weaknesses": "May be inflexible, judgmental, too focused on social status, not good with emotions"
            },
            "ESFJ": {
                "title": "The Consul",
                "description": "ESFJs are caring, social, and popular people who value harmony and cooperation. They're attentive to others' needs and often serve as the glue in their communities.",
                "strengths": "Strong people skills, reliable, practical, sensitive to others, loyal",
                "weaknesses": "Can be vulnerable to criticism, inflexible, needy for approval"
            },
            "ISTP": {
                "title": "The Virtuoso",
                "description": "ISTPs are daring experimenters with an aptitude for understanding how mechanical things work. They're practical problem solvers who enjoy hands-on activities.",
                "strengths": "Optimistic, creative, practical, spontaneous, rational in crisis",
                "weaknesses": "Can be private, insensitive, easily bored, risk-prone"
            },
            "ISFP": {
                "title": "The Adventurer",
                "description": "ISFPs are artistic, sensitive explorers who value personal freedom and expression. They enjoy new experiences and have a strong aesthetic sense.",
                "strengths": "Charming, sensitive to others, creative, passionate, artistic",
                "weaknesses": "May be unpredictable, too independent, easily stressed, or conflict-avoidant"
            },
            "ESTP": {
                "title": "The Entrepreneur",
                "description": "ESTPs are energetic thrill-seekers who enjoy acting on immediate, practical solutions. They're adaptable, observant, and enjoy living in the moment.",
                "strengths": "Bold, resourceful, rational, practical, observant, excellent in crisis",
                "weaknesses": "Can be impatient, risk-prone, unstructured, or defiant of rules"
            },
            "ESFP": {
                "title": "The Entertainer",
                "description": "ESFPs are vibrant, enthusiastic people who enjoy being in the spotlight and bringing joy to others. They're spontaneous, energetic, and enjoy living in the moment.",
                "strengths": "Bold, original, aesthetic, practical, observant, excellent people skills",
                "weaknesses": "May be sensitive to criticism, unfocused, or have difficulty with planning"
            }
        }
        
        # Return description for the given MBTI type
        return descriptions.get(mbti_type, {
            "title": "Personality Type",
            "description": "Each personality type has its own unique strengths and areas for growth.",
            "strengths": "Each type has different strengths",
            "weaknesses": "Each type has different challenges"
        })
