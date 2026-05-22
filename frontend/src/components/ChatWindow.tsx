/**
 * 对话窗口组件
 */

import React, { useRef, useEffect } from 'react';
import { useChatStore } from '../store';
import MessageItem from './MessageItem';
import ProcessTimeline from './ProcessTimeline';
import '../styles/ChatWindow.css';

interface ChatWindowProps {
  onCopy?: (content: string) => void;
}

const ChatWindow: React.FC<ChatWindowProps> = ({ onCopy }) => {
  const messages = useChatStore(state => state.messages);
  const turns = useChatStore(state => state.turns);
  const stateLogs = useChatStore(state => state.stateLogs);
  const sessionStatus = useChatStore(state => state.sessionStatus);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const toolsEndRef = useRef<HTMLDivElement>(null);

  const scrollMessagesToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const scrollToolsToBottom = () => {
    toolsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollMessagesToBottom();
  }, [messages]);

  useEffect(() => {
    scrollToolsToBottom();
  }, [stateLogs]);

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
      <div className="conversation-layout">
        <section className="conversation-panel text-panel" aria-label="对话文本">
          <div className="panel-header">
            <div>
              <h2>对话</h2>
              <p>{messages.length} 条消息</p>
            </div>
          </div>

          <div className="messages-container">
            {messages.map((message, idx) => {
              // Show turn divider when a user message matches a turn's request
              const turnForMsg = turns.find(
                t => t.user_request === message.content && message.role === 'user'
              );
              const prevMsg = idx > 0 ? messages[idx - 1] : null;
              const isNewTurn = turnForMsg && (!prevMsg || prevMsg.role !== 'user' || prevMsg.content !== turnForMsg.user_request);

              return (
                <React.Fragment key={message.id}>
                  {isNewTurn && turnForMsg && (
                    <div className="turn-divider">
                      <span className="turn-badge">第 {turnForMsg.turn_id} 轮</span>
                      {turnForMsg.score != null && (
                        <span className="turn-score">评分 {turnForMsg.score}/10</span>
                      )}
                      {turnForMsg.output_image_base64 && (
                        <img
                          className="turn-thumbnail"
                          src={turnForMsg.output_image_base64}
                          alt={`第 ${turnForMsg.turn_id} 轮输出`}
                        />
                      )}
                    </div>
                  )}
                  <MessageItem
                    message={message}
                    onCopy={onCopy}
                    showDetails={false}
                  />
                </React.Fragment>
              );
            })}
            <div ref={messagesEndRef} />
          </div>
        </section>

        <aside className="conversation-panel tools-panel" aria-label="实时工具调用">
          <div className="panel-header">
            <div>
              <h2>工具调用</h2>
              <p>{stateLogs.length ? `${stateLogs.length} 个实时事件` : '等待运行输出'}</p>
            </div>
            <span className={`session-status status-${sessionStatus}`}>{sessionStatus}</span>
          </div>

          <div className="tools-container">
            {stateLogs.length > 0 ? (
              <ProcessTimeline logs={stateLogs} />
            ) : (
              <div className="tools-empty">
                <div className="tools-empty-title">暂无工具输出</div>
                <div className="tools-empty-description">运行开始后，agent 调用和中间结果会显示在这里</div>
              </div>
            )}
            <div ref={toolsEndRef} />
          </div>
        </aside>
      </div>
    </div>
  );
};

export default ChatWindow;
