document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const chatForm = document.getElementById('chatForm');
    const userInput = document.getElementById('userInput');
    const chatMessages = document.getElementById('chatMessages');
    const resetBtn = document.getElementById('resetBtn');
    const assessmentStatus = document.getElementById('assessmentStatus');
    const resultsSection = document.getElementById('resultsSection');
    const messageCounter = document.getElementById('messageCounter');
    const messageProgress = document.getElementById('messageProgress');
    
    // Progress bar elements
    const eiProgress = document.getElementById('eiProgress');
    const snProgress = document.getElementById('snProgress');
    const tfProgress = document.getElementById('tfProgress');
    const jpProgress = document.getElementById('jpProgress');
    
    // Confidence elements
    const eiConfidence = document.getElementById('eiConfidence');
    const snConfidence = document.getElementById('snConfidence');
    const tfConfidence = document.getElementById('tfConfidence');
    const jpConfidence = document.getElementById('jpConfidence');
    
    // Result elements
    const mbtiType = document.getElementById('mbtiType');
    const mbtiTitle = document.getElementById('mbtiTitle');
    const mbtiDescription = document.getElementById('mbtiDescription');
    const mbtiStrengths = document.getElementById('mbtiStrengths');
    const mbtiWeaknesses = document.getElementById('mbtiWeaknesses');
    
    // Reasoning elements
    const eiReasoning = document.getElementById('eiReasoning');
    const snReasoning = document.getElementById('snReasoning');
    const tfReasoning = document.getElementById('tfReasoning');
    const jpReasoning = document.getElementById('jpReasoning');
    
    // Init state
    let isWaitingForResponse = false;
    let typingIndicator = null;
    
    // Handle sending user messages
    chatForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const message = userInput.value.trim();
        
        if (message && !isWaitingForResponse) {
            // Add user message to chat
            addMessage('user', message);
            
            // Clear input
            userInput.value = '';
            
            // Show typing indicator
            showTypingIndicator();
            
            // Send message to backend
            sendMessage(message);
        }
    });
    
    // Reset chat button
    resetBtn.addEventListener('click', function() {
        resetChat();
    });
    
    // Add message to chat
    function addMessage(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('chat-message', `${role}-message`);
        
        const messageContent = document.createElement('div');
        messageContent.classList.add('message-content');
        
        // Parse message content for line breaks
        const formattedContent = content.replace(/\n/g, '<br>');
        messageContent.innerHTML = `<p>${formattedContent}</p>`;
        
        messageDiv.appendChild(messageContent);
        chatMessages.appendChild(messageDiv);
        
        // Scroll to bottom
        scrollToBottom();
    }
    
    // Show typing indicator
    function showTypingIndicator() {
        isWaitingForResponse = true;
        
        // Create typing indicator if it doesn't exist
        if (!typingIndicator) {
            typingIndicator = document.createElement('div');
            typingIndicator.classList.add('chat-message', 'assistant-message');
            
            const indicator = document.createElement('div');
            indicator.classList.add('typing-indicator');
            indicator.innerHTML = '<span></span><span></span><span></span>';
            
            typingIndicator.appendChild(indicator);
        }
        
        chatMessages.appendChild(typingIndicator);
        scrollToBottom();
    }
    
    // Hide typing indicator
    function hideTypingIndicator() {
        if (typingIndicator && typingIndicator.parentNode === chatMessages) {
            chatMessages.removeChild(typingIndicator);
        }
        isWaitingForResponse = false;
    }
    
    // Scroll chat to bottom
    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    // Send message to backend
    function sendMessage(message) {
        fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: message })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            // Hide typing indicator
            hideTypingIndicator();
            
            // Add assistant message
            addMessage('assistant', data.response);
            
            // 메시지 진행도 표시 기능 제거
            // 내부적으로는 계속 추적하지만 UI에는 표시하지 않음
            
            // Update assessment progress bars
            updateAssessmentProgress(data.assessment_state);
            
            // Check if assessment is complete
            if (data.assessment_complete) {
                console.log("MBTI 평가 완료 감지됨");
                completeAssessment(data);
                
                // 추가 안전장치: 모달 직접 호출
                setTimeout(() => {
                    try {
                        const mbtiModal = document.getElementById('mbtiResultModal');
                        // 모달 데이터 설정
                        document.getElementById('modalMbtiType').textContent = data.mbti_type;
                        document.getElementById('modalMbtiTitle').textContent = data.mbti_description.title;
                        document.getElementById('modalMbtiDescription').textContent = data.mbti_description.description;
                        
                        // 전역 모달 인스턴스 사용 시도
                        if (window.mbtiResultModalInstance) {
                            window.mbtiResultModalInstance.show();
                        } else {
                            // 모달 직접 표시
                            const bsModal = new bootstrap.Modal(mbtiModal);
                            bsModal.show();
                        }
                    } catch (err) {
                        console.error("모달 표시 중 오류:", err);
                    }
                }, 1500);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            hideTypingIndicator();
            addMessage('assistant', 'Sorry, there was an error processing your message. Please try again.');
        });
    }
    
    // Update assessment progress bars
    function updateAssessmentProgress(assessmentState) {
        // E/I dimension
        const eiScore = assessmentState.E_I.score;
        const eiConfVal = assessmentState.E_I.confidence * 100;
        
        // Convert score from -1...1 to 0...100 for progress bar
        // Where 0 is fully I and 100 is fully E
        const eiPercent = ((eiScore + 1) / 2) * 100;
        eiProgress.style.width = `${eiPercent}%`;
        eiConfidence.textContent = `${Math.round(eiConfVal)}% confidence`;
        
        // S/N dimension
        const snScore = assessmentState.S_N.score;
        const snConfVal = assessmentState.S_N.confidence * 100;
        
        // Convert score from -1...1 to 0...100 for progress bar
        // Where 0 is fully S and 100 is fully N
        const snPercent = ((snScore + 1) / 2) * 100;
        snProgress.style.width = `${snPercent}%`;
        snConfidence.textContent = `${Math.round(snConfVal)}% confidence`;
        
        // T/F dimension
        const tfScore = assessmentState.T_F.score;
        const tfConfVal = assessmentState.T_F.confidence * 100;
        
        // Convert score from -1...1 to 0...100 for progress bar
        // Where 0 is fully T and 100 is fully F
        const tfPercent = ((tfScore + 1) / 2) * 100;
        tfProgress.style.width = `${tfPercent}%`;
        tfConfidence.textContent = `${Math.round(tfConfVal)}% confidence`;
        
        // J/P dimension
        const jpScore = assessmentState.J_P.score;
        const jpConfVal = assessmentState.J_P.confidence * 100;
        
        // Convert score from -1...1 to 0...100 for progress bar
        // Where 0 is fully J and 100 is fully P
        const jpPercent = ((jpScore + 1) / 2) * 100;
        jpProgress.style.width = `${jpPercent}%`;
        jpConfidence.textContent = `${Math.round(jpConfVal)}% confidence`;
        
        // Set colors based on confidence
        setProgressBarColors([
            { bar: eiProgress, confidence: assessmentState.E_I.confidence },
            { bar: snProgress, confidence: assessmentState.S_N.confidence },
            { bar: tfProgress, confidence: assessmentState.T_F.confidence },
            { bar: jpProgress, confidence: assessmentState.J_P.confidence }
        ]);
    }
    
    // Set progress bar colors based on confidence
    function setProgressBarColors(progressBars) {
        progressBars.forEach(item => {
            if (item.confidence < 0.3) {
                item.bar.classList.remove('bg-warning', 'bg-success');
                item.bar.classList.add('bg-danger');
            } else if (item.confidence < 0.7) {
                item.bar.classList.remove('bg-danger', 'bg-success');
                item.bar.classList.add('bg-warning');
            } else {
                item.bar.classList.remove('bg-danger', 'bg-warning');
                item.bar.classList.add('bg-success');
            }
        });
    }
    
    // Complete assessment and show results
    function completeAssessment(data) {
        // Update status
        assessmentStatus.textContent = '완료';
        assessmentStatus.classList.remove('bg-secondary');
        assessmentStatus.classList.add('bg-success');
        
        // Show results section
        resultsSection.classList.remove('d-none');
        
        // Update result content
        mbtiType.textContent = data.mbti_type;
        mbtiTitle.textContent = data.mbti_description.title;
        mbtiDescription.textContent = data.mbti_description.description;
        mbtiStrengths.textContent = data.mbti_description.strengths;
        mbtiWeaknesses.textContent = data.mbti_description.weaknesses;
        
        // Update reasoning content if available
        if (data.mbti_reasoning) {
            const reasoning = data.mbti_reasoning;
            
            // Format: "Label (score: X.XX, confidence: X.XX)"
            eiReasoning.textContent = `${reasoning.E_I.label} (점수: ${reasoning.E_I.score.toFixed(2)}, 확신도: ${(reasoning.E_I.confidence * 100).toFixed(0)}%)`;
            snReasoning.textContent = `${reasoning.S_N.label} (점수: ${reasoning.S_N.score.toFixed(2)}, 확신도: ${(reasoning.S_N.confidence * 100).toFixed(0)}%)`;
            tfReasoning.textContent = `${reasoning.T_F.label} (점수: ${reasoning.T_F.score.toFixed(2)}, 확신도: ${(reasoning.T_F.confidence * 100).toFixed(0)}%)`;
            jpReasoning.textContent = `${reasoning.J_P.label} (점수: ${reasoning.J_P.score.toFixed(2)}, 확신도: ${(reasoning.J_P.confidence * 100).toFixed(0)}%)`;
            
            // Add color coding based on confidence
            [
                { element: eiReasoning, confidence: reasoning.E_I.confidence },
                { element: snReasoning, confidence: reasoning.S_N.confidence },
                { element: tfReasoning, confidence: reasoning.T_F.confidence },
                { element: jpReasoning, confidence: reasoning.J_P.confidence }
            ].forEach(item => {
                item.element.classList.remove('text-danger', 'text-warning', 'text-success');
                if (item.confidence > 0.8) {
                    item.element.classList.add('text-success');
                } else if (item.confidence > 0.6) {
                    item.element.classList.add('text-warning');
                } else {
                    item.element.classList.add('text-danger');
                }
            });
        }
        
        console.log("MBTI 평가 완료: ", data.mbti_type);
        
        // 모달에 MBTI 결과 업데이트
        const modalType = document.getElementById('modalMbtiType');
        const modalTitle = document.getElementById('modalMbtiTitle');
        const modalDesc = document.getElementById('modalMbtiDescription');
        
        if (modalType) modalType.textContent = data.mbti_type;
        if (modalTitle) modalTitle.textContent = data.mbti_description.title;
        if (modalDesc) modalDesc.textContent = data.mbti_description.description;
        
        // 약간 지연 후 모달 표시
        setTimeout(() => {
            // 부트스트랩 5 방식으로 모달 표시
            const modalElement = document.getElementById('mbtiResultModal');
            if (modalElement) {
                const modal = new bootstrap.Modal(modalElement);
                modal.show();
                console.log("모달 표시 시도 완료");
            } else {
                console.error("모달 엘리먼트를 찾을 수 없음");
            }
        }, 1000);
    }
    
    // Reset chat
    function resetChat() {
        // Reset UI
        chatMessages.innerHTML = '';
        resultsSection.classList.add('d-none');
        assessmentStatus.textContent = 'In Progress';
        assessmentStatus.classList.remove('bg-success');
        assessmentStatus.classList.add('bg-secondary');
        
        // Reset progress bars
        eiProgress.style.width = '50%';
        snProgress.style.width = '50%';
        tfProgress.style.width = '50%';
        jpProgress.style.width = '50%';
        
        eiConfidence.textContent = '0% confidence';
        snConfidence.textContent = '0% confidence';
        tfConfidence.textContent = '0% confidence';
        jpConfidence.textContent = '0% confidence';
        
        // 메시지 진행도 관련 기능 제거
        
        [eiProgress, snProgress, tfProgress, jpProgress].forEach(bar => {
            bar.classList.remove('bg-danger', 'bg-warning', 'bg-success');
        });
        
        // Send reset request to backend
        fetch('/reset', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(() => {
            // Add initial message
            addMessage('assistant', '안녕하세요! 오늘 어떻게 지내고 계신가요? 편하게 대화하면서 서로 알아가 봐요.');
        })
        .catch(error => {
            console.error('Error:', error);
            addMessage('assistant', 'There was an error resetting the chat. Please refresh the page.');
        });
    }
    
    // Focus input field on page load
    userInput.focus();
});
