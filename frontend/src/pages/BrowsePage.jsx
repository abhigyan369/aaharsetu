import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { listingsApi } from '../services/api';
import { useAuth } from '../context/AuthContext';

export const BrowsePage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [claimStatusMsg, setClaimStatusMsg] = useState({ type: '', text: '' });

  // Filters
  const [foodTypeFilter, setFoodTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('available');
  const [sortByExpiry, setSortByExpiry] = useState(false);

  const fetchListings = async () => {
    try {
      setLoading(true);
      setError('');
      const params = {};
      if (foodTypeFilter) params.food_type = foodTypeFilter;
      if (statusFilter) params.status = statusFilter;

      const data = await listingsApi.getAll(params);
      let items = Array.isArray(data) ? data : (data.items || []);

      if (sortByExpiry) {
        items = [...items].sort((a, b) => {
          if (!a.expiry_time) return 1;
          if (!b.expiry_time) return -1;
          return new Date(a.expiry_time) - new Date(b.expiry_time);
        });
      }

      setListings(items);
    } catch (err) {
      setError(err.message || 'Failed to fetch listings.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchListings();
  }, [foodTypeFilter, statusFilter, sortByExpiry]);

  const handleClaim = async (listingId) => {
    if (!user) {
      navigate('/login');
      return;
    }

    if (user.role === 'donor') {
      setClaimStatusMsg({
        type: 'error',
        text: 'Only Receiver accounts can claim food listings. Please sign in as a receiver.'
      });
      return;
    }

    try {
      setClaimStatusMsg({ type: '', text: '' });
      await listingsApi.claim(listingId);
      setClaimStatusMsg({
        type: 'success',
        text: `Success! You have claimed listing #${listingId}. Please check details for pickup instructions.`
      });
      fetchListings();
    } catch (err) {
      setClaimStatusMsg({
        type: 'error',
        text: err.message || 'Failed to claim listing. It may already be claimed.'
      });
    }
  };

  return (
    <div className="container main-content">
      <div style={{ marginBottom: '2rem' }}>
        <h1 style={{ color: 'var(--color-primary)', marginBottom: '0.5rem' }}>Browse Available Food</h1>
        <p style={{ color: 'var(--color-text-muted)' }}>
          Discover surplus food near you, reserve portions, and reduce food waste in your community.
        </p>
      </div>

      {claimStatusMsg.text && (
        <div className={`alert alert-${claimStatusMsg.type}`}>
          {claimStatusMsg.text}
        </div>
      )}

      {/* Filter Bar */}
      <div className="card" style={{ marginBottom: '2rem', padding: '1.25rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', alignItems: 'center' }}>
          <div>
            <label className="form-label" htmlFor="foodTypeFilter">Food Category</label>
            <select
              id="foodTypeFilter"
              className="form-select"
              value={foodTypeFilter}
              onChange={(e) => setFoodTypeFilter(e.target.value)}
            >
              <option value="">All Categories</option>
              <option value="cooked">Cooked Food</option>
              <option value="packaged">Packaged Food</option>
              <option value="produce">Fresh Produce</option>
              <option value="bakery">Bakery Items</option>
              <option value="dairy">Dairy Products</option>
              <option value="beverage">Beverages</option>
              <option value="other">Other</option>
            </select>
          </div>

          <div>
            <label className="form-label" htmlFor="statusFilter">Status</label>
            <select
              id="statusFilter"
              className="form-select"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="available">Available Now</option>
              <option value="claimed">Claimed</option>
              <option value="">All Listings</option>
            </select>
          </div>

          <div>
            <label className="form-label">Sort Order</label>
            <button
              onClick={() => setSortByExpiry(!sortByExpiry)}
              className={`btn ${sortByExpiry ? 'btn-primary' : 'btn-outline'}`}
              style={{ width: '100%' }}
            >
              {sortByExpiry ? '⏰ Sorted by Expiry' : '⏳ Sort by Expiry Date'}
            </button>
          </div>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {/* Listings Grid */}
      {loading ? (
        <p style={{ textAlign: 'center', padding: '3rem 0' }}>Loading available food listings...</p>
      ) : listings.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '3rem 1.5rem', color: 'var(--color-text-muted)' }}>
          <h3>No listings found matching your criteria.</h3>
          <p style={{ marginTop: '0.5rem' }}>Try clearing filters or check back later!</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1.25rem' }}>
          {listings.map((item) => (
            <div key={item.id} className="card" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                <span className={`badge badge-${item.status}`}>{item.status}</span>
                <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', textTransform: 'capitalize' }}>
                  {item.food_type}
                </span>
              </div>

              <h3 style={{ fontSize: '1.2rem', marginBottom: '0.5rem' }}>
                <Link to={`/listings/${item.id}`}>{item.title}</Link>
              </h3>

              <p style={{ fontSize: '0.9rem', color: 'var(--color-text-muted)', marginBottom: '1rem', flex: 1 }}>
                {item.description || 'No description provided.'}
              </p>

              <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', borderTop: '1px solid var(--color-border)', paddingTop: '0.75rem', marginBottom: '1rem' }}>
                <div><strong>Quantity:</strong> {item.quantity} {item.quantity_unit || ''}</div>
                <div style={{ overflowWrap: 'break-word' }}><strong>Location:</strong> {item.address}</div>
                {item.expiry_time && (
                  <div><strong>Expires:</strong> {new Date(item.expiry_time).toLocaleString()}</div>
                )}
              </div>

              <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                <Link to={`/listings/${item.id}`} className="btn btn-outline" style={{ flex: 1, minWidth: '120px' }}>
                  View Details
                </Link>
                {item.status === 'available' && (
                  <button
                    onClick={() => handleClaim(item.id)}
                    className="btn btn-primary"
                    style={{ flex: 1, minWidth: '120px' }}
                  >
                    Claim Food
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
