/**
 * src/components/Chat/UnifiedChatWidget.jsx
 * ============================================
 * Unified Real-Time WebSocket Chat Box for Donors, Receivers, and Admins.
 */

import React, { useState, useEffect, useRef } from 'react';
import { MessageSquare } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { chatApi } from '../../services/api';
import './UnifiedChatWidget.css';

const CHANNELS = [
  { id: 'global', name: '🌐 Global Community', desc: 'Donors, Receivers & Admins' },
  { id: 'donor-receiver', name: '🥦 Donors & Receivers', desc: 'Direct food exchange discussion' },
  { id: 'admin-help', name: '🛡️ Admin Support Desk', desc: 'Help & Platform Moderation' },
];

export const UnifiedChatWidget = () => {
  const { user, token } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [activeChannel, setActiveChannel] = useState('global');
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [wsStatus, setWsStatus] = useState('disconnected'); // 'connecting' | 'connected' | 'disconnected'
  const [unreadCount, setUnreadCount] = useState(0);

  const socketRef = useRef(null);
  const messagesEndRef = useRef(null);

  // Scroll to bottom helper
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Fetch history when active channel changes or when opening chat
  useEffect(() => {
    if (!user) return;

    const loadHistory = async () => {
      try {
        const history = await chatApi.getHistory(activeChannel);
        setMessages(history);
      } catch (err) {
        console.error('Failed to load chat history:', err);
      }
    };

    loadHistory();
  }, [user, activeChannel]);

  // Connect WebSocket when user is logged in
  useEffect(() => {
    if (!user || !token) {
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
      setWsStatus('disconnected');
      return;
    }

    let isMounted = true;
    const wsUrl = `ws://localhost:8000/chat/ws?token=${encodeURIComponent(token)}`;

    setWsStatus('connecting');
    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.onopen = () => {
      if (isMounted) setWsStatus('connected');
    };

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === 'chat_message') {
          const newMsg = payload.data;
          setMessages((prev) => {
            // Prevent duplicates
            if (prev.some((m) => m.id === newMsg.id)) return prev;
            return [...prev, newMsg];
          });

          // Increment unread count if widget is closed
          if (!isOpen) {
            setUnreadCount((count) => count + 1);
          }
        }
      } catch (e) {
        console.error('Failed to parse WS message:', e);
      }
    };

    ws.onerror = (err) => {
      console.error('WebSocket Error:', err);
    };

    ws.onclose = () => {
      if (isMounted) setWsStatus('disconnected');
    };

    return () => {
      isMounted = false;
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    };
  }, [user, token]);

  // Auto-scroll when messages update
  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, isOpen]);

  // Reset unread count when opening modal
  const handleToggle = () => {
    if (!isOpen) {
      setUnreadCount(0);
    }
    setIsOpen(!isOpen);
  };

  const handleSendMessage = (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || !socketRef.current || wsStatus !== 'connected') return;

    const payload = {
      message: inputMessage.trim(),
      channel_id: activeChannel,
    };

    socketRef.current.send(JSON.stringify(payload));
    setInputMessage('');
  };

  const getRoleBadge = (role) => {
    switch (role?.toLowerCase()) {
      case 'donor':
        return <span className="chat-role-badge role-donor">🌱 Donor</span>;
      case 'admin':
        return <span className="chat-role-badge role-admin">🛡️ Admin</span>;
      case 'receiver':
      default:
        return <span className="chat-role-badge role-receiver">🤲 Receiver</span>;
    }
  };

  const filteredMessages = messages.filter((m) => m.channel_id === activeChannel);

  return (
    <div className="unified-chat-widget">
      {/* Floating Toggle Button */}
      <button className="chat-trigger-btn" onClick={handleToggle} title="Community Real-time Chat">
        <MessageSquare className="w-5 h-5 text-white" />
        <span className="trigger-text">Live Chat</span>
        {unreadCount > 0 && <span className="unread-badge">{unreadCount}</span>}
        {wsStatus === 'connected' && <span className="online-indicator-dot" />}
      </button>

      {/* Chat Window Popup/Modal */}
      {isOpen && (
        <div className="chat-window">
          {/* Header */}
          <div className="chat-header">
            <div className="chat-header-title">
              <h3>Unified Live Chat</h3>
              <span className={`ws-status-badge status-${wsStatus}`}>
                <span className="status-dot" />
                {wsStatus === 'connected'
                  ? 'Real-Time Online'
                  : wsStatus === 'connecting'
                  ? 'Connecting...'
                  : 'Offline'}
              </span>
            </div>
            <button className="close-btn" onClick={() => setIsOpen(false)}>
              ✕
            </button>
          </div>

          {/* User Auth Banner or Channel Selector */}
          {!user ? (
            <div className="chat-auth-prompt">
              <p>🔒 Please log in to join the unified real-time chat with Donors, Receivers & Admins.</p>
            </div>
          ) : (
            <>
              {/* Channel Tabs */}
              <div className="channel-tabs">
                {CHANNELS.map((ch) => (
                  <button
                    key={ch.id}
                    className={`channel-tab ${activeChannel === ch.id ? 'active' : ''}`}
                    onClick={() => setActiveChannel(ch.id)}
                    title={ch.desc}
                  >
                    {ch.name}
                  </button>
                ))}
              </div>

              {/* Message History */}
              <div className="chat-messages-container">
                {filteredMessages.length === 0 ? (
                  <div className="empty-chat-state">
                    <span>💬</span>
                    <p>No messages yet in #{activeChannel}. Start the conversation!</p>
                  </div>
                ) : (
                  filteredMessages.map((msg) => {
                    const isOwnMessage = msg.sender_id === user?.id;
                    const timeStr = new Date(msg.created_at).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                    });

                    return (
                      <div
                        key={msg.id || `${msg.sender_id}-${msg.created_at}`}
                        className={`chat-message-bubble ${isOwnMessage ? 'own-message' : ''}`}
                      >
                        <div className="msg-meta">
                          <span className="sender-name">{isOwnMessage ? 'You' : msg.sender_name}</span>
                          {getRoleBadge(msg.sender_role)}
                          <span className="msg-time">{timeStr}</span>
                        </div>
                        <div className="msg-text">{msg.message}</div>
                      </div>
                    );
                  })
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Message Input Form */}
              <form className="chat-input-form" onSubmit={handleSendMessage}>
                <input
                  type="text"
                  placeholder={
                    wsStatus === 'connected'
                      ? `Message #${activeChannel}...`
                      : 'Connecting to chat...'
                  }
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  disabled={wsStatus !== 'connected'}
                />
                <button type="submit" disabled={!inputMessage.trim() || wsStatus !== 'connected'}>
                  Send 🚀
                </button>
              </form>
            </>
          )}
        </div>
      )}
    </div>
  );
};
