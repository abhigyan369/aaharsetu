import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { listingsApi } from '../services/api';
import { useAuth } from '../context/AuthContext';

export const ListingDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [listing, setListing] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionMsg, setActionMsg] = useState({ type: '', text: '' });
  const [actionLoading, setActionLoading] = useState(false);

  const fetchListing = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await listingsApi.getById(id);
      setListing(data);
    } catch (err) {
      setError(err.message || 'Listing not found.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchListing();
  }, [id]);

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

  return (
    <div className="container main-content" style={{ maxWidth: '800px' }}>
      <Link to="/browse" style={{ display: 'inline-block', marginBottom: '1.5rem', fontWeight: 500 }}>
        ← Back to all listings
      </Link>

      {actionMsg.text && (
        <div className={`alert alert-${actionMsg.type}`}>
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
          <p style={{ wordBreak: 'break-word' }}><strong>Address:</strong> {listing.address}</p>
          {listing.donor && (
            <p style={{ marginTop: '0.25rem', wordBreak: 'break-word' }}>
              <strong>Donated by:</strong> {listing.donor.name} ({listing.donor.email})
            </p>
          )}
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: '1rem', borderTop: '1px solid var(--color-border)', paddingTop: '1.25rem', flexWrap: 'wrap' }}>
          {listing.status === 'available' && !isOwner && (
            <button
              onClick={handleClaim}
              className="btn btn-primary"
              style={{ flex: 1, padding: '0.85rem', width: '100%' }}
              disabled={actionLoading}
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
