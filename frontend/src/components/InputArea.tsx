/**
 * 输入区域组件
 */

import React, { useState, useRef } from 'react';
import { useChatStore } from '../store';
import '../styles/InputArea.css';

interface InputAreaProps {
  onSendMessage: (message: string, enableSearch: boolean, file?: File) => void;
  isLoading?: boolean;
}

const InputArea: React.FC<InputAreaProps> = ({ onSendMessage, isLoading = false }) => {
  const [message, setMessage] = useState('');
  const [enableSearch, setEnableSearch] = useState(true);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const currentSessionId = useChatStore(state => state.currentSessionId);
  const turns = useChatStore(state => state.turns);
  const hasPriorOutput = turns.length > 0 && turns.some(t => t.output_path);

  const handleSendMessage = () => {
    if (!message.trim() && !selectedFile) {
      return;
    }

    if (!currentSessionId) {
      alert('请先创建或选择一个对话');
      return;
    }

    onSendMessage(message, enableSearch, selectedFile || undefined);

    // 清空输入
    setMessage('');
    setSelectedFile(null);
    setFilePreview(null);
    
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);

      // 生成预览
      const reader = new FileReader();
      reader.onload = (event) => {
        setFilePreview(event.target?.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleClearFile = () => {
    setSelectedFile(null);
    setFilePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value);

    // 自动调整高度
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
  };

  const handleTextareaKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Ctrl+Enter 或 Cmd+Enter 发送
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="input-area">
      {filePreview && (
        <div className="file-preview">
          <div className="preview-content">
            <img src={filePreview} alt="preview" />
            <button
              className="btn-remove-file"
              onClick={handleClearFile}
              title="移除文件"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      <div className="input-controls">
        <div className="control-left">
          <label className="file-input-label">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleFileChange}
              disabled={isLoading}
            />
            <span className="file-input-btn">📎 图片</span>
          </label>

          <label className="search-toggle">
            <input
              type="checkbox"
              checked={enableSearch}
              onChange={e => setEnableSearch(e.target.checked)}
              disabled={isLoading}
            />
            <span>启用检索</span>
          </label>
        </div>

        <div className="control-right">
          <span className="hint">Ctrl+Enter 发送</span>
        </div>
      </div>

      <textarea
        ref={textareaRef}
        className="message-input"
        placeholder="输入你的问题或指令... (Ctrl+Enter 发送)"
        value={message}
        onChange={handleTextareaChange}
        onKeyDown={handleTextareaKeyDown}
        disabled={isLoading}
        rows={3}
      />

      {hasPriorOutput && !selectedFile && (
        <div className="input-source-indicator">
          将基于上一轮输出图片继续处理（或上传新图片覆盖）
        </div>
      )}

      <div className="input-actions">
        <button
          className="btn-send"
          onClick={handleSendMessage}
          disabled={(!message.trim() && !selectedFile) || isLoading}
          title="发送消息 (Ctrl+Enter)"
        >
          {isLoading ? '⟳ 处理中...' : '发送'}
        </button>
      </div>
    </div>
  );
};

export default InputArea;
