import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { listingsApi } from '../services/api';
import { useAuth } from '../context/AuthContext';

export const DonorDashboardPage = () => {
  const { user } = useAuth();
  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionSuccess, setActionSuccess] = useState('');

  const fetchDonorListings = async () => {
    try {
      setLoading(true);
      // Fetch all listings and filter for current donor
      const data = await listingsApi.getAll();
      const items = Array.isArray(data) ? data : (data.items || []);
      const myItems = items.filter(item => item.donor_id === user?.id || item.donor?.id === user?.id);
      setListings(myItems);
    } catch (err) {
      setError(err.message || 'Failed to load your listings.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDonorListings();
  }, [user]);

  const handleMarkComplete = async (id) => {
    try {
      setActionSuccess('');
      setError('');
      await listingsApi.complete(id);
      setActionSuccess(`Listing #${id} marked as completed/picked up!`);
      fetchDonorListings();
    } catch (err) {
      setError(err.message || 'Failed to update listing status.');
    }
  };

  const activeCount = listings.filter(l => l.status === 'available').length;
  const completedCount = listings.filter(l => l.status === 'completed' || l.status === 'picked_up').length;

  return (
    <div className="container main-content">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 style={{ color: 'var(--color-primary)' }}>Donor Dashboard</h1>
          <p style={{ color: 'var(--color-text-muted)' }}>Manage your active surplus food postings and track distributions.</p>
        </div>
        <Link to="/listings/new" className="btn btn-primary w-full sm:w-auto text-center">
          + Create New Listing
        </Link>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {actionSuccess && <div className="alert alert-success">{actionSuccess}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1.25rem', marginBottom: '2rem' }}>
        <div className="card" style={{ borderLeft: '4px solid var(--color-primary)' }}>
          <h4 style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>TOTAL POSTED</h4>
          <p style={{ fontSize: '1.8rem', fontWeight: 700, marginTop: '0.25rem' }}>{listings.length}</p>
        </div>
        <div className="card" style={{ borderLeft: '4px solid var(--color-secondary)' }}>
          <h4 style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>ACTIVE LISTINGS</h4>
          <p style={{ fontSize: '1.8rem', fontWeight: 700, marginTop: '0.25rem', color: 'var(--color-primary)' }}>{activeCount}</p>
        </div>
        <div className="card" style={{ borderLeft: '4px solid var(--color-accent)' }}>
          <h4 style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>COMPLETED PICKUPS</h4>
          <p style={{ fontSize: '1.8rem', fontWeight: 700, marginTop: '0.25rem' }}>{completedCount}</p>
        </div>
      </div>

      <div className="card" style={{ padding: '1.5rem' }}>
        <h3 style={{ marginBottom: '1.25rem' }}>My Food Listings</h3>

        {loading ? (
          <p style={{ padding: '2rem 0', textAlign: 'center' }}>Loading your listings...</p>
        ) : listings.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '3rem 0', color: 'var(--color-text-muted)' }}>
            <p style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>You haven't posted any food listings yet.</p>
            <Link to="/listings/new" className="btn btn-secondary">Create Your First Listing</Link>
          </div>
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Category</th>
                  <th>Quantity</th>
                  <th>Status</th>
                  <th>Posted On</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {listings.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link to={`/listings/${item.id}`} style={{ fontWeight: 600 }}>
                        {item.title}
                      </Link>
                    </td>
                    <td><span style={{ textTransform: 'capitalize' }}>{item.food_type}</span></td>
                    <td>{item.quantity} {item.quantity_unit || ''}</td>
                    <td>
                      <span className={`badge badge-${item.status}`}>
                        {item.status}
                      </span>
                    </td>
                    <td>{new Date(item.created_at).toLocaleDateString()}</td>
                    <td>
                      {item.status === 'available' || item.status === 'claimed' ? (
                        <button
                          onClick={() => handleMarkComplete(item.id)}
                          className="btn btn-outline btn-sm"
                        >
                          Mark Completed
                        </button>
                      ) : (
                        <span style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>Completed</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
