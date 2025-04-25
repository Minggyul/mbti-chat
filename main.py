import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# 로깅 설정 
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Flask 앱 초기화
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")

# DB 설정
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# SQLAlchemy 초기화
db = SQLAlchemy(app)

# 데이터베이스 모델 가져오기
from models import Conversation, Message, QuestionLog

# app.py에서 라우트 가져오기
from app import init_routes

# 데이터베이스 테이블 생성
with app.app_context():
    db.create_all()
    logger.info("데이터베이스 테이블이 생성되었습니다.")

# 라우트 초기화
init_routes(app)

if __name__ == "__main__":
    # 앱 실행
    app.run(host="0.0.0.0", port=5000, debug=True)
