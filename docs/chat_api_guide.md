# 채팅 API 사용 가이드

이 문서는 Nebula AI 채팅 API를 사용하여 클라이언트를 개발하는 방법을 설명합니다.

## 📋 API 개요

### 주요 엔드포인트
- `POST /chat/sessions` - 새 채팅 세션 생성
- `POST /chat/stream` - 채팅 스트리밍 (SSE)
- `GET /chat/sessions` - 사용자 세션 목록 조회
- `GET /chat/sessions/{session_id}/messages` - 세션 메시지 조회

## 🚀 기본 사용 흐름

### 1. 새 대화 시작

#### Option A: 세션 먼저 생성 (권장)
```javascript
// 1. 새 세션 생성
const sessionResponse = await fetch('/chat/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        user_id: 123,
        title: "AI와의 대화"
    })
});
const { session_id } = await sessionResponse.json();

// 2. 해당 세션으로 채팅
const response = await fetch('/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        user_id: 123,
        message: "안녕하세요!",
        session_id: session_id  // 기존 세션 연결
    })
});
```

#### Option B: 바로 채팅 시작 (자동 세션 생성)
```javascript
const response = await fetch('/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        user_id: 123,
        message: "안녕하세요!"
        // session_id 없음 -> 새 세션 자동 생성
    })
});
```

### 2. SSE 스트림 처리

```javascript
const eventSource = new EventSource('/chat/stream', {
    method: 'POST',
    body: JSON.stringify(requestData)
});

let currentSessionId = null;
let currentMessage = "";

eventSource.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    switch(data.type) {
        case 'session_start':
            // 🆕 세션 정보 즉시 수신
            currentSessionId = data.data.session_id;
            console.log('세션 시작:', currentSessionId);
            break;
            
        case 'chunk':
            // AI 응답 실시간 스트리밍
            currentMessage += data.data;
            updateUI(currentMessage);
            break;
            
        case 'session_end':
            // 응답 완료
            console.log('세션 완료:', data.session_id);
            console.log('AI 메시지 ID:', data.ai_message_id);
            saveSessionId(currentSessionId); // 다음 요청을 위해 저장
            break;
            
        case 'error':
            console.error('오류:', data.data);
            break;
    }
};
```

### 3. 기존 대화 이어가기

```javascript
// 저장된 세션 ID로 연속 대화
const continueChat = async (sessionId, newMessage) => {
    const response = await fetch('/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            user_id: 123,
            message: newMessage,
            session_id: sessionId  // 기존 세션 연결
        })
    });
    
    // SSE 처리...
};
```

## 📊 메시지 저장 구조

### 사용자 메시지
- 요청과 동시에 즉시 저장됨
- `role: "user"`
- `session_start` 이벤트에서 `user_message_id` 제공

### AI 응답 메시지  
- 스트리밍 완료 후 저장됨
- `role: "assistant"`
- `session_end` 이벤트에서 `ai_message_id` 제공

## 🔄 세션 관리 베스트 프랙티스

### 1. 세션 ID 저장
```javascript
// LocalStorage 활용
const saveSessionId = (sessionId) => {
    localStorage.setItem('current_chat_session', sessionId);
};

const getCurrentSessionId = () => {
    return localStorage.getItem('current_chat_session');
};
```

### 2. 세션 목록 조회
```javascript
const getUserSessions = async (userId) => {
    const response = await fetch(`/chat/sessions?user_id=${userId}&limit=20`);
    return await response.json();
};
```

### 3. 메시지 히스토리 조회
```javascript
const getSessionMessages = async (sessionId, userId) => {
    const response = await fetch(`/chat/sessions/${sessionId}/messages?user_id=${userId}`);
    return await response.json();
};
```

## 🛡️ 중복 방지

### Idempotency Key 사용
```javascript
const chatWithIdempotency = async (message, sessionId = null) => {
    const idempotencyKey = generateUUID(); // 고유 키 생성
    
    const response = await fetch('/chat/stream', {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'idempotency-key': idempotencyKey  // 중복 방지 키
        },
        body: JSON.stringify({
            user_id: 123,
            message: message,
            session_id: sessionId
        })
    });
};
```

## 🎨 UI 구현 예시

### React 컴포넌트 예시
```jsx
import { useState, useEffect } from 'react';

const ChatComponent = ({ userId }) => {
    const [sessionId, setSessionId] = useState(null);
    const [messages, setMessages] = useState([]);
    const [currentMessage, setCurrentMessage] = useState('');
    const [isStreaming, setIsStreaming] = useState(false);

    const sendMessage = async (text) => {
        if (isStreaming) return;
        
        setIsStreaming(true);
        setCurrentMessage('');
        
        // 사용자 메시지 즉시 표시
        setMessages(prev => [...prev, { role: 'user', content: text }]);
        
        const response = await fetch('/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: userId,
                message: text,
                session_id: sessionId
            })
        });
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = JSON.parse(line.substring(6));
                    
                    switch (data.type) {
                        case 'session_start':
                            setSessionId(data.data.session_id);
                            break;
                            
                        case 'chunk':
                            setCurrentMessage(prev => prev + data.data);
                            break;
                            
                        case 'session_end':
                            setMessages(prev => [...prev, { 
                                role: 'assistant', 
                                content: currentMessage 
                            }]);
                            setCurrentMessage('');
                            setIsStreaming(false);
                            break;
                    }
                }
            }
        }
    };

    return (
        <div className="chat-container">
            <div className="messages">
                {messages.map((msg, idx) => (
                    <div key={idx} className={`message ${msg.role}`}>
                        {msg.content}
                    </div>
                ))}
                {isStreaming && currentMessage && (
                    <div className="message assistant streaming">
                        {currentMessage}
                    </div>
                )}
            </div>
            
            <ChatInput onSend={sendMessage} disabled={isStreaming} />
        </div>
    );
};
```

## ⚠️ 주의사항

1. **세션 ID 관리**: 클라이언트에서 세션 ID를 적절히 저장하고 관리해야 연속 대화가 가능합니다.

2. **스트림 처리**: SSE 연결이 끊어질 수 있으므로 재연결 로직을 구현하세요.

3. **오류 처리**: 네트워크 오류, API 오류 등에 대한 적절한 처리가 필요합니다.

4. **성능**: 긴 대화에서는 메시지 히스토리를 적절히 관리하여 메모리 사용량을 최적화하세요.

## 🔧 테스트

### cURL 예시
```bash
# 1. 새 세션 생성
curl -X POST "http://localhost:8000/chat/sessions" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 123, "title": "테스트 대화"}'

# 2. 채팅 (SSE 스트림)
curl -X POST "http://localhost:8000/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 123, "message": "안녕하세요!", "session_id": "세션ID"}' \
  --no-buffer

# 3. 세션 목록 조회
curl "http://localhost:8000/chat/sessions?user_id=123&limit=10"

# 4. 메시지 히스토리 조회
curl "http://localhost:8000/chat/sessions/세션ID/messages?user_id=123"
```

이제 클라이언트에서 **연속 대화**가 가능하며, 세션 관리가 훨씬 명확해졌습니다! 🎉 