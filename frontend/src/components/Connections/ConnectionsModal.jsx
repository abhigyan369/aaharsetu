import React, { useState, useEffect } from 'react';
import { UserCheck, UserPlus, X, Check, XCircle, MessageSquare } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { connectionsApi } from '../../services/api';
import './ConnectionsModal.css';

export const ConnectionsModal = ({ isOpen, onClose, onOpenPrivateChat }) => {
  const { user } = useAuth();
  const [connections, setConnections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('incoming'); // 'incoming' | 'connected' | 'all'
  const [actionLoadingId, setActionLoadingId] = useState(null);

  const fetchConnections = async () => {
    if (!user) return;
    try {
      setLoading(true);
      setError('');
      const data = await connectionsApi.getConnections();
      setConnections(data);
    } catch (err) {
      setError(err.message || 'Failed to load connections.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchConnections();
    }
  }, [isOpen, user]);

  if (!isOpen || !user) return null;

  const handleAccept = async (connId) => {
    try {
      setActionLoadingId(connId);
      await connectionsApi.acceptRequest(connId);
      await fetchConnections();
    } catch (err) {
      alert(err.message || 'Failed to accept connection request.');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleDecline = async (connId) => {
    try {
      setActionLoadingId(connId);
      await connectionsApi.declineRequest(connId);
      await fetchConnections();
    } catch (err) {
      alert(err.message || 'Failed to decline request.');
    } finally {
      setActionLoadingId(null);
    }
  };

  const incomingRequests = connections.filter(
    (c) => c.status === 'pending' && c.addressee_id === user.id
  );

  const outgoingRequests = connections.filter(
    (c) => c.status === 'pending' && c.requester_id === user.id
  );

  const acceptedConnections = connections.filter((c) => c.status === 'accepted');

  return (
    <div className="connections-modal-overlay">
      <div className="connections-modal">
        <div className="connections-header">
          <div className="flex items-center gap-2">
            <UserCheck className="w-5 h-5 text-[#2D6A4F]" />
            <h2>Donor-Receiver Connections</h2>
          </div>
          <button className="connections-close-btn" onClick={onClose}>
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="connections-tabs">
          <button
            className={`tab-btn ${activeTab === 'incoming' ? 'active' : ''}`}
            onClick={() => setActiveTab('incoming')}
          >
            Pending Requests ({incomingRequests.length})
          </button>
          <button
            className={`tab-btn ${activeTab === 'connected' ? 'active' : ''}`}
            onClick={() => setActiveTab('connected')}
          >
            Connected ({acceptedConnections.length})
          </button>
          <button
            className={`tab-btn ${activeTab === 'outgoing' ? 'active' : ''}`}
            onClick={() => setActiveTab('outgoing')}
          >
            Sent Requests ({outgoingRequests.length})
          </button>
        </div>

        <div className="connections-body">
          {loading ? (
            <div className="connections-loading">Loading connections...</div>
          ) : error ? (
            <div className="connections-error">{error}</div>
          ) : (
            <>
              {/* Incoming Pending Requests */}
              {activeTab === 'incoming' && (
                <div className="connections-list">
                  {incomingRequests.length === 0 ? (
                    <div className="empty-state">
                      <UserPlus className="w-8 h-8 text-gray-400 mb-2" />
                      <p>No pending connection requests.</p>
                    </div>
                  ) : (
                    incomingRequests.map((conn) => {
                      const peer = conn.requester;
                      return (
                        <div key={conn.id} className="connection-card">
                          <div className="peer-info">
                            <div className="peer-avatar">
                              {peer?.name?.charAt(0).toUpperCase() || 'U'}
                            </div>
                            <div>
                              <h4 className="peer-name">{peer?.name}</h4>
                              <span className="peer-role-badge">
                                {peer?.role === 'donor' ? '🌱 Donor' : '🤲 Receiver'}
                              </span>
                            </div>
                          </div>
                          <div className="action-buttons">
                            <button
                              className="btn-accept"
                              onClick={() => handleAccept(conn.id)}
                              disabled={actionLoadingId === conn.id}
                            >
                              <Check className="w-4 h-4" /> Accept
                            </button>
                            <button
                              className="btn-decline"
                              onClick={() => handleDecline(conn.id)}
                              disabled={actionLoadingId === conn.id}
                            >
                              <XCircle className="w-4 h-4" /> Decline
                            </button>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              )}

              {/* Connected Users */}
              {activeTab === 'connected' && (
                <div className="connections-list">
                  {acceptedConnections.length === 0 ? (
                    <div className="empty-state">
                      <UserCheck className="w-8 h-8 text-gray-400 mb-2" />
                      <p>No connected users yet.</p>
                      <small className="text-gray-500">
                        {user.role === 'receiver'
                          ? 'Send a connection request to a food donor on their listing page!'
                          : 'Receivers can send you connection requests, or you can connect with them!'}
                      </small>
                    </div>
                  ) : (
                    acceptedConnections.map((conn) => {
                      const isUserRequester = conn.requester_id === user.id;
                      const peer = isUserRequester ? conn.addressee : conn.requester;
                      const channelId = `private_${conn.donor_id}_${conn.receiver_id}`;

                      return (
                        <div key={conn.id} className="connection-card">
                          <div className="peer-info">
                            <div className="peer-avatar connected">
                              {peer?.name?.charAt(0).toUpperCase() || 'U'}
                            </div>
                            <div>
                              <h4 className="peer-name">{peer?.name}</h4>
                              <span className="peer-role-badge">
                                {peer?.role === 'donor' ? '🌱 Donor' : '🤲 Receiver'}
                              </span>
                            </div>
                          </div>
                          <button
                            className="btn-chat"
                            onClick={() => {
                              onClose();
                              if (onOpenPrivateChat) {
                                onOpenPrivateChat(channelId, peer?.name);
                              }
                            }}
                          >
                            <MessageSquare className="w-4 h-4" /> Private Chat
                          </button>
                        </div>
                      );
                    })
                  )}
                </div>
              )}

              {/* Outgoing Requests */}
              {activeTab === 'outgoing' && (
                <div className="connections-list">
                  {outgoingRequests.length === 0 ? (
                    <div className="empty-state">
                      <p>No sent pending connection requests.</p>
                    </div>
                  ) : (
                    outgoingRequests.map((conn) => {
                      const peer = conn.addressee;
                      return (
                        <div key={conn.id} className="connection-card">
                          <div className="peer-info">
                            <div className="peer-avatar">
                              {peer?.name?.charAt(0).toUpperCase() || 'U'}
                            </div>
                            <div>
                              <h4 className="peer-name">{peer?.name}</h4>
                              <span className="peer-role-badge">
                                {peer?.role === 'donor' ? '🌱 Donor' : '🤲 Receiver'}
                              </span>
                            </div>
                          </div>
                          <span className="status-badge pending">Waiting for response ⏳</span>
                        </div>
                      );
                    })
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};
