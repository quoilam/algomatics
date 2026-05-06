/**
 * 对话窗口组件
 */

import React, { useRef, useEffect } from 'react';
import { useChatStore } from '../store';
import MessageItem from './MessageItem';
import '../styles/ChatWindow.css';

interface ChatWindowProps {
  onCopy?: (content: string) => void;
}

const ChatWindow: React.FC<ChatWindowProps> = ({ onCopy }) => {
  const messages = useChatStore(state => state.messages);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  if (!messages || messages.length === 0) {
    return (
      <div className="chat-window empty-state">
        <div className="empty-content">
          <div className="empty-icon">💬</div>
          <div className="empty-title">开始对话</div>
          <div className="empty-description">在下方输入你的问题或指令</div>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-window">
      <div className="messages-container">
        {messages.map(message => (
          <MessageItem
            key={message.id}
            message={message}
            onCopy={onCopy}
          />
        ))}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
};

export default ChatWindow;
