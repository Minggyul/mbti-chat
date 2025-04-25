from datetime import datetime
from sqlalchemy import String, Text, DateTime, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column
from main import db

class Conversation(db.Model):
    """대화 세션 정보를 저장하는 모델""" 
    __tablename__ = "conversations"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    assessment_state: Mapped[dict] = mapped_column(JSON, default=dict)
    is_complete: Mapped[bool] = mapped_column(default=False)
    message_count: Mapped[int] = mapped_column(default=0)
    last_focus_dimension: Mapped[str] = mapped_column(String(10), nullable=True)
    mbti_result: Mapped[str] = mapped_column(String(4), nullable=True)
    
    def __repr__(self):
        return f"<Conversation {self.session_id}>"


class Message(db.Model):
    """개별 메시지를 저장하는 모델"""
    __tablename__ = "messages"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(db.ForeignKey("conversations.id"))
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'user' or 'assistant'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    dimension_scores: Mapped[dict] = mapped_column(JSON, nullable=True)  # 메시지에 대한 MBTI 분석 결과 저장
    
    def __repr__(self):
        return f"<Message {self.id} ({self.role})>"


class QuestionLog(db.Model):
    """AI가 물었던 질문들을 기록하는 모델"""
    __tablename__ = "question_logs"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(db.ForeignKey("conversations.id"))
    question: Mapped[str] = mapped_column(Text, nullable=False)
    dimension: Mapped[str] = mapped_column(String(10), nullable=False)  # 'E_I', 'S_N', 'T_F', 'J_P'
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<QuestionLog {self.id} ({self.dimension})>"
