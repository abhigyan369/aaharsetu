/**
 * src/components/Chat/UnifiedChatWidget.jsx
 * ============================================
 * Unified Real-Time WebSocket & Private Chat Box for Donors, Receivers, and Admins.
 */

import React, { useState, useEffect, useRef } from 'react';
import { MessageSquare, Lock, ChevronLeft, UserCheck } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { chatApi, connectionsApi } from '../../services/api';
import './UnifiedChatWidget.css';

const PUBLIC_CHANNELS = [
  { id: 'global', name: '🌐 Global', desc: 'Public Community' },
  { id: 'donor-receiver', name: '🥦 Food Exchange', desc: 'Public Exchange' },
  { id: 'admin-help', name: '🛡️ Support', desc: 'Admin Desk' },
  { id: 'private', name: '🔒 Private DM', desc: 'Private 1-on-1 Chats' },
];

export const UnifiedChatWidget = () => {
  const { user, token } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [activeChannel, setActiveChannel] = useState('global');
  const [privatePeerName, setPrivatePeerName] = useState('');
  const [connectedUsers, setConnectedUsers] = useState([]);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [wsStatus, setWsStatus] = useState('disconnected');
  const [unreadCount, setUnreadCount] = useState(0);

  const socketRef = useRef(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Listen for custom 'open_private_chat' event from other components
  useEffect(() => {
    const handleOpenPrivateChat = (e) => {
      const { channelId, peerName } = e.detail || {};
      if (channelId) {
        setIsOpen(true);
        setActiveChannel(channelId);
        if (peerName) setPrivatePeerName(peerName);
      }
    };

    window.addEventListener('open_private_chat', handleOpenPrivateChat);
    return () => window.removeEventListener('open_private_chat', handleOpenPrivateChat);
  }, []);

  // Fetch accepted connections when private tab is clicked
  useEffect(() => {
    if (!user) return;
    if (activeChannel === 'private') {
      const loadConnectedUsers = async () => {
        try {
          const list = await connectionsApi.getConnections('accepted');
          setConnectedUsers(list);
        } catch (err) {
          console.error('Failed to load connected users:', err);
        }
      };
      loadConnectedUsers();
    }
  }, [user, activeChannel]);

  // Fetch history when active channel changes
  useEffect(() => {
    if (!user || activeChannel === 'private') return;

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

    let wsUrl = '';
    if (import.meta.env.VITE_WS_URL) {
      wsUrl = `${import.meta.env.VITE_WS_URL}/chat/ws?token=${encodeURIComponent(token)}`;
    } else {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      let host = window.location.host;
      let pathPrefix = '/api';
      if (import.meta.env.VITE_API_BASE_URL) {
        try {
          const url = new URL(import.meta.env.VITE_API_BASE_URL, window.location.origin);
          host = url.host;
          pathPrefix = url.pathname === '/' ? '' : url.pathname;
        } catch (e) {}
      }
      wsUrl = `${protocol}//${host}${pathPrefix}/chat/ws?token=${encodeURIComponent(token)}`;
    }

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
            if (prev.some((m) => m.id === newMsg.id)) return prev;
            return [...prev, newMsg];
          });

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

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, isOpen]);

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
  const isPrivateChannel = activeChannel.startsWith('private_');

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
              <h3>
                {isPrivateChannel
                  ? `🔒 Private: ${privatePeerName || 'Direct Message'}`
                  : 'Unified Live Chat'}
              </h3>
              <span className={`ws-status-badge status-${wsStatus}`}>
                <span className="status-dot" />
                {wsStatus === 'connected' ? 'Online' : wsStatus === 'connecting' ? 'Connecting...' : 'Offline'}
              </span>
            </div>
            <button className="close-btn" onClick={() => setIsOpen(false)}>
              ✕
            </button>
          </div>

          {!user ? (
            <div className="chat-auth-prompt">
              <p>🔒 Please log in to join the unified real-time chat with Donors, Receivers & Admins.</p>
            </div>
          ) : (
            <>
              {/* Channel Tabs */}
              <div className="channel-tabs">
                {PUBLIC_CHANNELS.map((ch) => (
                  <button
                    key={ch.id}
                    className={`channel-tab ${
                      activeChannel === ch.id || (ch.id === 'private' && isPrivateChannel) ? 'active' : ''
                    }`}
                    onClick={() => {
                      setActiveChannel(ch.id);
                      if (ch.id !== 'private') setPrivatePeerName('');
                    }}
                    title={ch.desc}
                  >
                    {ch.name}
                  </button>
                ))}
              </div>

              {/* Private Connections Selection Screen */}
              {activeChannel === 'private' ? (
                <div className="private-users-selector">
                  <div className="selector-title">Select a connected partner to chat:</div>
                  {connectedUsers.length === 0 ? (
                    <div className="empty-chat-state">
                      <UserCheck className="w-8 h-8 text-gray-400 mb-2" />
                      <p>No connected users yet.</p>
                      <small>Connect with a donor or receiver first to unlock private messaging!</small>
                    </div>
                  ) : (
                    <div className="connected-users-list">
                      {connectedUsers.map((conn) => {
                        const isRequester = conn.requester_id === user.id;
                        const peer = isRequester ? conn.addressee : conn.requester;
                        const chId = `private_${conn.donor_id}_${conn.receiver_id}`;

                        return (
                          <button
                            key={conn.id}
                            className="connected-user-item"
                            onClick={() => {
                              setActiveChannel(chId);
                              setPrivatePeerName(peer?.name || 'User');
                            }}
                          >
                            <div className="avatar">{peer?.name?.charAt(0).toUpperCase()}</div>
                            <div className="details">
                              <div className="name">{peer?.name}</div>
                              <div className="role">{peer?.role}</div>
                            </div>
                            <MessageSquare className="w-4 h-4 text-emerald-600 ml-auto" />
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              ) : (
                <>
                  {isPrivateChannel && (
                    <div className="private-channel-bar">
                      <button className="back-btn" onClick={() => setActiveChannel('private')}>
                        <ChevronLeft className="w-4 h-4" /> All Private Chats
                      </button>
                    </div>
                  )}

                  {/* Message History */}
                  <div className="chat-messages-container">
                    {filteredMessages.length === 0 ? (
                      <div className="empty-chat-state">
                        <span>💬</span>
                        <p>
                          {isPrivateChannel
                            ? `Private channel with ${privatePeerName}. Say hi!`
                            : `No messages yet in #${activeChannel}. Start the conversation!`}
                        </p>
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
                          ? isPrivateChannel
                            ? `Private message to ${privatePeerName}...`
                            : `Message #${activeChannel}...`
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
            </>
          )}
        </div>
      )}
    </div>
  );
};
