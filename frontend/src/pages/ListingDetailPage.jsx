import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { listingsApi, connectionsApi } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { UserCheck, UserPlus, MessageSquare, AlertCircle } from 'lucide-react';

export const ListingDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [listing, setListing] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionMsg, setActionMsg] = useState({ type: '', text: '' });
  const [actionLoading, setActionLoading] = useState(false);

  // Connection state for receivers viewing donor's listing
  const [connStatus, setConnStatus] = useState({ status: 'none', connection_id: null });
  const [connLoading, setConnLoading] = useState(false);

  const fetchListing = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await listingsApi.getById(id);
      setListing(data);

      const donorId = data.donor_id || data.donor?.id;
      if (user && donorId && user.id !== donorId) {
        fetchConnectionStatus(donorId);
      }
    } catch (err) {
      setError(err.message || 'Listing not found.');
    } finally {
      setLoading(false);
    }
  };

  const fetchConnectionStatus = async (donorId) => {
    try {
      const res = await connectionsApi.getStatus(donorId);
      setConnStatus(res);
    } catch (e) {
      console.error('Failed to fetch connection status:', e);
    }
  };

  useEffect(() => {
    fetchListing();
  }, [id, user?.id]);

  const handleSendConnectionRequest = async () => {
    const donorId = listing.donor_id || listing.donor?.id;
    if (!donorId) return;

    try {
      setConnLoading(true);
      setActionMsg({ type: '', text: '' });
      await connectionsApi.sendRequest(donorId);
      setActionMsg({ type: 'success', text: 'Connection request sent to donor!' });
      await fetchConnectionStatus(donorId);
    } catch (err) {
      setActionMsg({ type: 'error', text: err.message || 'Failed to send connection request.' });
    } finally {
      setConnLoading(false);
    }
  };

  const handleAcceptConnection = async () => {
    if (!connStatus.connection_id) return;
    try {
      setConnLoading(true);
      await connectionsApi.acceptRequest(connStatus.connection_id);
      setActionMsg({ type: 'success', text: 'Connection accepted! You can now claim food from this donor.' });
      const donorId = listing.donor_id || listing.donor?.id;
      await fetchConnectionStatus(donorId);
    } catch (err) {
      setActionMsg({ type: 'error', text: err.message || 'Failed to accept connection.' });
    } finally {
      setConnLoading(false);
    }
  };

  const handleClaim = async () => {
    if (!user) {
      navigate('/login');
      return;
    }

    try {
      setActionLoading(true);
      setActionMsg({ type: '', text: '' });
      await listingsApi.claim(id);
      setActionMsg({ type: 'success', text: 'Listing successfully claimed! Please coordinate pickup.' });
      fetchListing();
    } catch (err) {
      setActionMsg({ type: 'error', text: err.message || 'Failed to claim listing.' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleComplete = async () => {
    try {
      setActionLoading(true);
      setActionMsg({ type: '', text: '' });
      await listingsApi.complete(id);
      setActionMsg({ type: 'success', text: 'Listing marked as completed/picked up.' });
      fetchListing();
    } catch (err) {
      setActionMsg({ type: 'error', text: err.message || 'Failed to complete listing.' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleOpenPrivateChat = () => {
    const donorId = listing.donor_id || listing.donor?.id;
    const receiverId = user.id;
    const channelId = `private_${donorId}_${receiverId}`;
    const chatTrigger = document.querySelector('.chat-trigger-btn');
    if (chatTrigger) {
      chatTrigger.click();
      window.dispatchEvent(
        new CustomEvent('open_private_chat', {
          detail: { channelId, peerName: listing.donor?.name || 'Donor' },
        })
      );
    }
  };

  if (loading) {
    return (
      <div className="container main-content" style={{ textAlign: 'center', padding: '4rem 0' }}>
        <p>Loading food listing details...</p>
      </div>
    );
  }

  if (error || !listing) {
    return (
      <div className="container main-content">
        <div className="alert alert-error">
          {error || 'Listing not found.'}
        </div>
        <Link to="/browse" className="btn btn-outline">← Back to Browse</Link>
      </div>
    );
  }

  const isOwner = user && (user.id === listing.donor_id || user.id === listing.donor?.id);
  const isReceiver = user && user.role === 'receiver';

  return (
    <div className="container main-content" style={{ maxWidth: '800px' }}>
      <Link to="/browse" style={{ display: 'inline-block', marginBottom: '1.5rem', fontWeight: 500 }}>
        ← Back to all listings
      </Link>

      {actionMsg.text && (
        <div className={`alert alert-${actionMsg.type}`} style={{ marginBottom: '1.25rem' }}>
          {actionMsg.text}
        </div>
      )}

      <div className="card" style={{ padding: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '1.25rem' }}>
          <div>
            <span className={`badge badge-${listing.status}`} style={{ marginBottom: '0.5rem' }}>
              {listing.status}
            </span>
            <h1 style={{ color: 'var(--color-primary)', fontSize: '1.6rem', lineHeight: 1.25 }}>{listing.title}</h1>
          </div>
          <span style={{ fontSize: '0.9rem', background: '#f3f4f6', padding: '0.35rem 0.75rem', borderRadius: 'var(--radius-md)', textTransform: 'capitalize' }}>
            Category: <strong>{listing.food_type}</strong>
          </span>
        </div>

        {listing.image_url && (
          <div style={{ marginBottom: '1.5rem', borderRadius: 'var(--radius-md)', overflow: 'hidden', maxHeight: '300px' }}>
            <img
              src={listing.image_url}
              alt={listing.title}
              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
            />
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '1rem', backgroundColor: '#f8f9fa', padding: '1rem', borderRadius: 'var(--radius-md)', marginBottom: '1.5rem' }}>
          <div>
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: 'block' }}>QUANTITY</span>
            <strong style={{ fontSize: '1rem' }}>{listing.quantity} {listing.quantity_unit || ''}</strong>
          </div>
          <div>
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: 'block' }}>EXPIRY TIME</span>
            <strong style={{ fontSize: '1rem' }}>
              {listing.expiry_time ? new Date(listing.expiry_time).toLocaleString() : 'Not specified'}
            </strong>
          </div>
          <div>
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: 'block' }}>POSTED ON</span>
            <strong style={{ fontSize: '1rem' }}>{new Date(listing.created_at).toLocaleDateString()}</strong>
          </div>
        </div>

        <div style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ marginBottom: '0.5rem', color: 'var(--color-primary)' }}>Description</h3>
          <p style={{ lineHeight: 1.6, color: 'var(--color-text)' }}>
            {listing.description || 'No additional description provided by the donor.'}
          </p>
        </div>

        <div style={{ marginBottom: '1.5rem', borderTop: '1px solid var(--color-border)', paddingTop: '1.25rem' }}>
          <h3 style={{ marginBottom: '0.5rem', color: 'var(--color-primary)' }}>Pickup Information</h3>
          <p style={{ wordBreak: 'break-word' }}><strong>Address:</strong> {listing.address || 'Pickup address provided upon claim'}</p>
          {listing.latitude && listing.longitude && (
            <p style={{ marginTop: '0.25rem', color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
              📍 <strong>OpenStreetMap Coordinates:</strong> Lat {listing.latitude}, Lon {listing.longitude}
            </p>
          )}
          {listing.donor && (
            <p style={{ marginTop: '0.25rem', wordBreak: 'break-word' }}>
              <strong>Donated by:</strong> {listing.donor.name} ({listing.donor.email})
            </p>
          )}
        </div>

        {/* Connection Requirement Box for Receivers */}
        {isReceiver && !isOwner && listing.status === 'available' && (
          <div style={{ marginBottom: '1.5rem', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid #e5e7eb', backgroundColor: connStatus.status === 'accepted' ? '#f0fdf4' : '#fffbe6' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                {connStatus.status === 'accepted' ? (
                  <UserCheck className="w-5 h-5 text-emerald-600" />
                ) : (
                  <AlertCircle className="w-5 h-5 text-amber-600" />
                )}
                <div>
                  <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, color: connStatus.status === 'accepted' ? '#065f46' : '#92400e' }}>
                    {connStatus.status === 'accepted'
                      ? 'Connected with Donor ✅'
                      : connStatus.status === 'pending_sent'
                      ? 'Connection Request Sent ⏳'
                      : connStatus.status === 'pending_received'
                      ? 'Donor Sent You a Request! 🤝'
                      : 'Connection Required to Claim Food'}
                  </h4>
                  <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.8rem', color: connStatus.status === 'accepted' ? '#047857' : '#b45309' }}>
                    {connStatus.status === 'accepted'
                      ? 'You are connected with this donor. You can claim food and chat directly!'
                      : connStatus.status === 'pending_sent'
                      ? 'Waiting for the donor to accept your connection request before claiming.'
                      : connStatus.status === 'pending_received'
                      ? 'Click Accept below to establish connection and claim this food listing.'
                      : 'You must connect with the donor before you can claim this food listing.'}
                  </p>
                </div>
              </div>

              {connStatus.status === 'none' && (
                <button
                  onClick={handleSendConnectionRequest}
                  disabled={connLoading}
                  className="btn btn-primary"
                  style={{ fontSize: '0.85rem', padding: '0.5rem 1rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
                >
                  <UserPlus className="w-4 h-4" /> {connLoading ? 'Sending...' : 'Connect with Donor'}
                </button>
              )}

              {connStatus.status === 'pending_received' && (
                <button
                  onClick={handleAcceptConnection}
                  disabled={connLoading}
                  className="btn btn-primary"
                  style={{ fontSize: '0.85rem', padding: '0.5rem 1rem' }}
                >
                  {connLoading ? 'Accepting...' : 'Accept Request'}
                </button>
              )}

              {connStatus.status === 'accepted' && (
                <button
                  onClick={handleOpenPrivateChat}
                  className="btn btn-outline"
                  style={{ fontSize: '0.85rem', padding: '0.5rem 1rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
                >
                  <MessageSquare className="w-4 h-4 text-emerald-600" /> Private Chat
                </button>
              )}
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: '1rem', borderTop: '1px solid var(--color-border)', paddingTop: '1.25rem', flexWrap: 'wrap' }}>
          {listing.status === 'available' && !isOwner && (
            <button
              onClick={handleClaim}
              className="btn btn-primary"
              style={{ flex: 1, padding: '0.85rem', width: '100%' }}
              disabled={actionLoading || (isReceiver && connStatus.status !== 'accepted')}
              title={isReceiver && connStatus.status !== 'accepted' ? 'Connection required before claiming food' : ''}
            >
              {actionLoading ? 'Claiming...' : 'Claim Surplus Food 🍲'}
            </button>
          )}

          {(listing.status === 'available' || listing.status === 'claimed') && isOwner && (
            <button
              onClick={handleComplete}
              className="btn btn-secondary"
              style={{ flex: 1, padding: '0.85rem', width: '100%' }}
              disabled={actionLoading}
            >
              {actionLoading ? 'Updating...' : 'Mark as Completed / Picked Up'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
