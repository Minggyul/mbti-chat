import logging
import json
import uuid
from datetime import datetime
from flask import render_template, request, jsonify, session
from mbti_analyzer import MBTIAnalyzer
from main import db
from models import Conversation, Message, QuestionLog

# Configure logging
logger = logging.getLogger(__name__)

# MBTI analyzer 초기화
mbti_analyzer = MBTIAnalyzer()

# Flask 앱에 라우트를 추가하는 함수
def init_routes(app):
    
    @app.route('/')
    def index():
        """
        메인 채팅 인터페이스를 렌더링하고 세션을 초기화합니다.
        기존 세션이 있으면 세션 ID를 유지하고, 없으면 새로운 세션을 생성합니다.
        """
        # 세션 ID가 없으면 새로운 세션 ID 생성
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        
        session_id = session['session_id']
        
        # 세션 ID로 기존 대화 불러오기 또는 새로운 대화 생성
        conversation_record = Conversation.query.filter_by(session_id=session_id).first()
        
        if not conversation_record:
            # 새로운 대화 생성
            initial_assessment_state = {
                'E_I': {'score': 0, 'confidence': 0},
                'S_N': {'score': 0, 'confidence': 0},
                'T_F': {'score': 0, 'confidence': 0},
                'J_P': {'score': 0, 'confidence': 0}
            }
            
            # 대화 세션 저장
            conversation_record = Conversation(
                session_id=session_id,
                assessment_state=initial_assessment_state,
                is_complete=False,
                message_count=0,
            )
            db.session.add(conversation_record)
            db.session.commit()
            
            # 세션 변수 초기화
            session['conversation'] = []
            session['assessment_state'] = initial_assessment_state
            session['assessment_complete'] = False
            session['message_count'] = 0
            session['min_messages_needed'] = 10
            session['last_focus_dimension'] = None
            session['conversation_id'] = conversation_record.id
        else:
            # 기존 대화 불러오기
            messages = Message.query.filter_by(conversation_id=conversation_record.id).order_by(Message.timestamp).all()
            
            # 대화 내용을 세션에 복원
            conversation = []
            for msg in messages:
                conversation.append({"role": msg.role, "content": msg.content})
            
            # 세션 변수 업데이트
            session['conversation'] = conversation
            session['assessment_state'] = conversation_record.assessment_state
            session['assessment_complete'] = conversation_record.is_complete
            session['message_count'] = conversation_record.message_count
            session['min_messages_needed'] = 10
            session['last_focus_dimension'] = conversation_record.last_focus_dimension
            session['conversation_id'] = conversation_record.id
        
        return render_template('index.html')
    
    @app.route('/chat', methods=['POST'])
    def chat():
        """Process user message and return AI response."""
        try:
            # Get user message from request
            data = request.get_json()
            user_message = data.get('message', '')
            
            # 세션 정보 가져오기
            session_id = session.get('session_id')
            conversation_id = session.get('conversation_id')
            
            if not session_id or not conversation_id:
                logger.error("세션 ID 또는 대화 ID가 없습니다")
                return jsonify({"error": "세션이 만료되었습니다. 페이지를 새로고침해주세요."}), 400
            
            # DB에서 현재 대화 세션 불러오기
            conversation_record = Conversation.query.get(conversation_id)
            if not conversation_record:
                logger.error(f"대화 ID {conversation_id}를 찾을 수 없습니다")
                return jsonify({"error": "대화를 찾을 수 없습니다. 페이지를 새로고침해주세요."}), 404
            
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
            
            # 사용자 메시지를 DB에 저장
            user_message_record = Message(
                conversation_id=conversation_id,
                role="user",
                content=user_message
            )
            db.session.add(user_message_record)
            db.session.commit()
            
            # Update message count
            message_count = session.get('message_count', 0) + 1
            session['message_count'] = message_count
            
            # Process message through MBTI analyzer
            min_messages_needed = session.get('min_messages_needed', 10)
            last_focus_dimension = session.get('last_focus_dimension', None)
            
            response, updated_assessment_state, assessment_complete, new_focus_dimension = mbti_analyzer.process_message(
                user_message, 
                conversation,
                assessment_state,
                assessment_complete,
                message_count,
                min_messages_needed,
                last_focus_dimension
            )
            
            # Update the last focus dimension in session
            session['last_focus_dimension'] = new_focus_dimension
            
            # Add AI response to conversation history
            conversation.append({"role": "assistant", "content": response})
            
            # AI 응답을 DB에 저장
            assistant_message_record = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=response
            )
            db.session.add(assistant_message_record)
            
            # 대화 세션 업데이트
            conversation_record.assessment_state = updated_assessment_state
            conversation_record.is_complete = assessment_complete
            conversation_record.message_count = message_count
            conversation_record.last_focus_dimension = new_focus_dimension
            
            if assessment_complete:
                mbti_type = mbti_analyzer.calculate_mbti_type(updated_assessment_state)
                conversation_record.mbti_result = mbti_type
            
            db.session.commit()
            
            # 시스템이 물어본 질문이 있을 경우, 질문 로깅 (간단한 휴리스틱 사용)
            # 응답에서 마지막 물음표가 있는 문장을 찾음
            if '?' in response:
                # 마지막 질문을 추출
                sentences = response.split('.')
                for sentence in reversed(sentences):
                    if '?' in sentence:
                        question = sentence.strip()
                        # 질문과 초점 차원을 로깅
                        if new_focus_dimension:
                            question_log = QuestionLog(
                                conversation_id=conversation_id,
                                question=question,
                                dimension=new_focus_dimension
                            )
                            db.session.add(question_log)
                            db.session.commit()
                        break
            
            # Update session
            session['conversation'] = conversation
            session['assessment_state'] = updated_assessment_state
            session['assessment_complete'] = assessment_complete
            
            # Prepare response
            min_messages = session.get('min_messages_needed', 10)
            result = {
                "response": response,
                "assessment_state": updated_assessment_state,
                "assessment_complete": assessment_complete,
                "message_count": message_count,
                "min_messages_needed": min_messages,
                "progress_percentage": min(100, int(message_count / min_messages * 100))
            }
            
            if assessment_complete:
                # Calculate MBTI type when assessment is complete
                mbti_type = mbti_analyzer.calculate_mbti_type(updated_assessment_state)
                mbti_description = mbti_analyzer.get_mbti_description(mbti_type)
                
                # Add reasoning for each dimension
                reasoning = {
                    'E_I': {
                        'label': "외향적" if updated_assessment_state['E_I']['score'] > 0 else "내향적",
                        'score': abs(updated_assessment_state['E_I']['score']),
                        'confidence': updated_assessment_state['E_I']['confidence']
                    },
                    'S_N': {
                        'label': "감각적" if updated_assessment_state['S_N']['score'] < 0 else "직관적",
                        'score': abs(updated_assessment_state['S_N']['score']),
                        'confidence': updated_assessment_state['S_N']['confidence']
                    },
                    'T_F': {
                        'label': "사고적" if updated_assessment_state['T_F']['score'] < 0 else "감정적",
                        'score': abs(updated_assessment_state['T_F']['score']),
                        'confidence': updated_assessment_state['T_F']['confidence']
                    },
                    'J_P': {
                        'label': "판단적" if updated_assessment_state['J_P']['score'] < 0 else "인식적",
                        'score': abs(updated_assessment_state['J_P']['score']),
                        'confidence': updated_assessment_state['J_P']['confidence']
                    }
                }
                
                result["mbti_type"] = mbti_type
                result["mbti_description"] = mbti_description
                result["mbti_reasoning"] = reasoning
            
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"Error in chat endpoint: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/reset', methods=['POST'])
    def reset():
        """Reset the conversation and assessment state."""
        try:
            # 기존 세션 ID 유지하면서 새 대화 시작
            session_id = session.get('session_id')
            if not session_id:
                session['session_id'] = str(uuid.uuid4())
                session_id = session['session_id']
            
            # 대화 초기화
            initial_assessment_state = {
                'E_I': {'score': 0, 'confidence': 0},
                'S_N': {'score': 0, 'confidence': 0},
                'T_F': {'score': 0, 'confidence': 0},
                'J_P': {'score': 0, 'confidence': 0}
            }
            
            # 이전 대화 세션이 있는지 확인
            conversation_record = Conversation.query.filter_by(session_id=session_id).first()
            
            if conversation_record:
                # 새 대화 생성 (기존 대화와 세션 ID는 동일)
                conversation_record = Conversation(
                    session_id=session_id,
                    assessment_state=initial_assessment_state,
                    is_complete=False,
                    message_count=0
                )
                db.session.add(conversation_record)
                db.session.commit()
                session['conversation_id'] = conversation_record.id
            else:
                # 첫 대화 세션 생성
                conversation_record = Conversation(
                    session_id=session_id,
                    assessment_state=initial_assessment_state,
                    is_complete=False,
                    message_count=0
                )
                db.session.add(conversation_record)
                db.session.commit()
                session['conversation_id'] = conversation_record.id
            
            # 세션 상태 초기화
            session['conversation'] = []
            session['assessment_state'] = initial_assessment_state
            session['assessment_complete'] = False
            session['message_count'] = 0
            session['last_focus_dimension'] = None
            
            return jsonify({"status": "success", "message": "대화가 초기화되었습니다."})
        
        except Exception as e:
            logger.error(f"대화 초기화 중 오류 발생: {str(e)}")
            return jsonify({"error": str(e)}), 500