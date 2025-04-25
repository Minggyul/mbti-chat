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
        self.confidence_threshold = 0.7  # 첫 메시지에서 확신도가 0.7보다 높아질 수 없도록 설정됨

    def process_message(self, user_message, conversation, assessment_state, assessment_complete, message_count=0, min_messages_needed=5, last_focus_dimension=None):
        """
        Process user message and update MBTI assessment state.
        
        Args:
            user_message (str): The user's message
            conversation (list): Conversation history
            assessment_state (dict): Current MBTI assessment scores and confidence
            assessment_complete (bool): Whether assessment is complete
            message_count (int): Current number of user messages
            min_messages_needed (int): Minimum number of user messages required for assessment (기본값 5개로 변경)
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
                    
                    # 신뢰도를 매우 낮은 비율로 증가시킴
                    # 메시지 5개 안에서는 신뢰도가 크게 높아지지 않도록 0.05의 매우 낮은 증가율 사용
                    new_confidence = min(current['confidence'] + 0.05, 0.7)  # 0.05씩만 증가, 최대 0.7
                    
                    updated_assessment[dimension] = {
                        'score': weighted_score,
                        'confidence': new_confidence
                    }
            
            return updated_assessment
            
        except Exception as e:
            logger.error(f"Error analyzing MBTI traits: {str(e)}")
            # Return original assessment if analysis fails
            return current_assessment

    def _check_assessment_complete(self, assessment, message_count=0, min_messages_needed=5):
        """
        Check if MBTI assessment is complete based on confidence thresholds and
        minimum number of messages.
        
        Args:
            assessment (dict): Current MBTI assessment state
            message_count (int): Current number of user messages
            min_messages_needed (int): Minimum number of user messages required (기본값 5개로 변경)
            
        Returns:
            bool: True if assessment is complete, False otherwise
        """
        # Check if minimum message count is reached
        if message_count < min_messages_needed:
            return False
            
        # 충분한 메시지 수(5개)에 도달했다면, 다음 경우에 완료로 간주:
        # 1. 모든 차원이 신뢰도 임계값을 넘은 경우 (기존 조건)
        # 2. 메시지 카운트가 min_messages_needed에 도달한 경우 (추가 조건)
        
        # 신뢰도가 낮은 차원 개수 확인
        low_confidence_dimensions = 0
        for dimension, values in assessment.items():
            if values['confidence'] < self.confidence_threshold:
                low_confidence_dimensions += 1
        
        # 1. 모든 차원이 신뢰도 임계값을 넘은 경우
        if low_confidence_dimensions == 0:
            return True
        
        # 2. 메시지 카운트가 정확히 min_messages_needed에 도달한 경우 (5개 메시지) - 강제 완료
        # 단, 첫 대화는 시스템 메시지이므로 정확히 5개가 채워졌을 때 완료하도록 조건 설정 (>=가 아닌 ==)
        if message_count == min_messages_needed:
            logger.debug(f"메시지 개수 {message_count}개로 MBTI 평가 완료 (강제)")
            return True
        
        return False

    def _generate_response(self, user_message, conversation, assessment, is_complete, message_count=0, min_messages_needed=5, last_focus_dimension=None):
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
            
            # 대화의 맥락에 맞게 자연스럽게 물어볼 수 있는 질문들
            target_questions = {
                'E_I': [
                    "혹시 주말에는 주로 어떻게 시간을 보내세요? 친구들과 만나는 걸 즐기시나요, 아니면 조용히 혼자만의 시간을 갖는 걸 선호하시나요?",
                    "대화하다 보니 궁금한데요, 새로운 사람들을 만날 때 어떤 느낌이 드세요? 설레는 편인가요, 아니면 조금 긴장되시나요?",
                    "요즘 바쁘게 지내시는 것 같은데, 스트레스 해소는 어떻게 하시나요? 혼자 조용히 쉬는 게 좋으신가요, 아니면 다른 사람들과 어울리면서 에너지를 충전하시나요?",
                    "오늘 이야기를 나누면서 느꼈는데요, 큰 모임에서 여러 사람들과 대화할 때와 소수의 친한 사람들과 깊은 대화를 나눌 때 어느 쪽이 더 편하세요?"
                ],
                'S_N': [
                    "방금 말씀하신 내용을 들으니 궁금한데요, 새로운 정보를 접할 때 구체적인 사실에 집중하시나요, 아니면 그 정보가 가진 의미나 가능성을 더 먼저 생각하시나요?",
                    "그런 상황에서는 어떻게 대처하셨어요? 보통 문제를 해결할 때 경험이나 사실에 기반해서 접근하시나요, 아니면 직관이나 가능성을 탐색하는 편이신가요?",
                    "말씀하신 취미가 흥미롭네요. 새로운 것을 배울 때 단계별로 차근차근 배우는 걸 선호하시나요, 아니면 큰 그림을 먼저 파악하고 시작하는 편인가요?",
                    "이 대화를 통해 서로를 알아가는 것도 재미있는 과정 같은데요, 평소에 미래에 대해 생각할 때 구체적인 계획을 세우시는 편인가요, 아니면 다양한 가능성을 열어두시나요?"
                ],
                'T_F': [
                    "아까 말씀하신 경험이 인상적이네요. 그런 중요한 결정을 내릴 때 주로 논리와 사실에 기반해서 결정하시나요, 아니면 사람들의 감정이나 가치를 더 중요하게 생각하시나요?",
                    "흥미로운 관점이세요. 누군가와 의견이 다를 때는 보통 어떻게 대화하시나요? 객관적인 사실을 중심으로 이야기하시나요, 아니면 서로의 감정과 조화를 더 중요시하시나요?",
                    "방금 하신 이야기가 공감이 가네요. 주변 사람들이 당신에 대해 어떻게 표현하나요? 논리적이고 분석적이라고 하나요, 아니면 배려심이 깊고 공감을 잘한다고 하나요?",
                    "오늘 대화가 정말 즐겁네요. 평소 갈등 상황에서는 어떻게 대처하시나요? 문제를 논리적으로 해결하는 걸 중요시하시나요, 아니면 관계의 조화를 더 중요하게 생각하시나요?"
                ],
                'J_P': [
                    "그런 이야기를 들으니 더 궁금해지는데요, 일상생활에서 계획을 세우고 그대로 진행하는 걸 선호하시나요, 아니면 상황에 따라 유연하게 대처하는 편이신가요?",
                    "말씀하신 내용이 흥미롭네요. 여행 가실 때는 어떠세요? 일정을 미리 꼼꼼하게 계획하시나요, 아니면 현지에서 즉흥적으로 결정하는 걸 즐기시나요?",
                    "대화하면서 느꼈는데요, 마감 기한이 있는 일을 할 때 어떤 방식으로 진행하시나요? 미리 계획해서 차근차근 진행하시나요, 아니면 마감 직전에 집중해서 하시나요?",
                    "지금까지 나눈 대화를 보니 궁금한데요, 주변 환경이 정돈되어 있는 걸 중요하게 생각하시나요, 아니면 약간의 혼란스러움이 있어도 크게 신경 쓰지 않으시나요?"
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
            당신은 자연스럽게 대화하면서 사용자의 MBTI 성격 유형을 파악하는 친근한 챗봇입니다. 
            사용자의 성격 특성을 드러내는 대화를 이끌어내는 것이 목표입니다.
            
            현재 평가 상태:
            E/I: 점수 {assessment['E_I']['score']:.2f}, 확신도 {assessment['E_I']['confidence']:.2f}
            S/N: 점수 {assessment['S_N']['score']:.2f}, 확신도 {assessment['S_N']['confidence']:.2f}
            T/F: 점수 {assessment['T_F']['score']:.2f}, 확신도 {assessment['T_F']['confidence']:.2f}
            J/P: 점수 {assessment['J_P']['score']:.2f}, 확신도 {assessment['J_P']['confidence']:.2f}
            
            메시지 수: {message_count}/{min_messages_needed}
            더 평가가 필요한 차원: {", ".join(low_confidence_dimensions)}
            
            가장 낮은 확신도를 가진 차원: {focus_dimension}
            
            다음은 이 차원을 평가하는 데 사용할 수 있는 자연스러운 질문들입니다:
            {target_questions[focus_dimension]}
            
            가이드라인:
            1. 대화가 자연스럽게 흘러가야 함 - 평가 중임이 드러나지 않도록 유의
            2. 이전 대화의 맥락을 활용하여 자연스럽게 새로운 질문으로 연결
            3. 단순히 나열된 질문을 그대로 하지 말고, 대화의 흐름에 맞게 적절히 수정하여 질문
            4. 사용자의 메시지에 먼저 충분히 반응한 후, 자연스럽게 다음 질문으로 이어갈 것
            5. 대화가 부자연스럽게 느껴지지 않도록 주의
            6. 공감과 호감을 표현하며 편안한 대화 분위기 조성
            7. 너무 갑작스러운 주제 전환은 피할 것
            
            친구와 대화하듯 자연스럽게 대화를 이어가되, 사용자의 성격 특성에 관한 정보를 전략적으로 얻어내세요.
            대화의 맥락과 흐름을 매우 중요하게 생각하고, 자연스러운 대화를 최우선으로 하세요.
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
            return "죄송합니다, 대화를 이어가는 데 어려움이 있네요. 대화를 계속해 볼까요? 오늘 어떻게 지내고 계신가요?", None

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
