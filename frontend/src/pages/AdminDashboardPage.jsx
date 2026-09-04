import React, { useState, useEffect } from 'react';
import { adminApi } from '../services/api';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Doughnut, Line } from 'react-chartjs-2';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend
);

export const AdminDashboardPage = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setLoading(true);
        setError('');
        const data = await adminApi.getStats();
        setStats(data);
      } catch (err) {
        setError(err.message || 'Failed to fetch admin stats. Ensure you are logged in as an admin.');
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, []);

  if (loading) {
    return (
      <div className="container main-content" style={{ textAlign: 'center', padding: '4rem 0' }}>
        <p>Loading platform analytics...</p>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="container main-content">
        <div className="alert alert-error">
          {error || 'Unable to load statistics.'}
        </div>
      </div>
    );
  }

  // 1. Food Type Doughnut Chart Data
  const foodTypeChartData = {
    labels: stats.food_type_labels || [],
    datasets: [
      {
        label: 'Food Listings',
        data: stats.food_type_counts || [],
        backgroundColor: [
          '#2D6A4F',
          '#52B788',
          '#D8A838',
          '#74C69D',
          '#95D5B2',
          '#B7E4C7',
          '#D8F3DC',
        ],
        borderWidth: 1,
      },
    ],
  };

  // 2. 30-Day Time Series Line Chart Data
  const timeSeriesChartData = {
    labels: stats.timeseries_labels || [],
    datasets: [
      {
        label: 'Listings Created',
        data: stats.timeseries_counts || [],
        borderColor: '#2D6A4F',
        backgroundColor: 'rgba(45, 106, 79, 0.1)',
        tension: 0.3,
        fill: true,
        pointRadius: 3,
      },
    ],
  };

  return (
    <div className="container main-content">
      <div style={{ marginBottom: '2rem' }}>
        <h1 style={{ color: 'var(--color-primary)', marginBottom: '0.25rem' }}>Admin Analytics Dashboard</h1>
        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem' }}>
          Platform metrics generated at {stats.generated_at || 'Just now'}
        </p>
      </div>

      {/* Overview Stat Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
        <div className="card" style={{ borderTop: '4px solid var(--color-primary)' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>TOTAL LISTINGS</span>
          <p style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--color-text)', marginTop: '0.25rem' }}>
            {stats.total_listings}
          </p>
        </div>

        <div className="card" style={{ borderTop: '4px solid var(--color-secondary)' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>ACTIVE LISTINGS</span>
          <p style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--color-primary)', marginTop: '0.25rem' }}>
            {stats.active_listings}
          </p>
        </div>

        <div className="card" style={{ borderTop: '4px solid var(--color-accent)' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>MEALS SAVED</span>
          <p style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--color-text)', marginTop: '0.25rem' }}>
            {stats.completed_pickups}
          </p>
        </div>

        <div className="card" style={{ borderTop: '4px solid #3b82f6' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>DONORS</span>
          <p style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--color-text)', marginTop: '0.25rem' }}>
            {stats.total_donors}
          </p>
        </div>

        <div className="card" style={{ borderTop: '4px solid #8b5cf6' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>RECEIVERS</span>
          <p style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--color-text)', marginTop: '0.25rem' }}>
            {stats.total_receivers}
          </p>
        </div>
      </div>

      {/* Charts Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem' }}>
        <div className="card" style={{ padding: '1.25rem' }}>
          <h3 style={{ color: 'var(--color-primary)', marginBottom: '1rem', textAlign: 'center', fontSize: '1.1rem' }}>
            Food Type Breakdown
          </h3>
          <div style={{ height: '260px', display: 'flex', justifyContent: 'center' }}>
            {stats.food_type_labels?.length > 0 ? (
              <Doughnut data={foodTypeChartData} options={{ responsive: true, maintainAspectRatio: false }} />
            ) : (
              <p style={{ color: 'var(--color-text-muted)', padding: '2rem 0' }}>No food type data available.</p>
            )}
          </div>
        </div>

        <div className="card" style={{ padding: '1.25rem' }}>
          <h3 style={{ color: 'var(--color-primary)', marginBottom: '1rem', textAlign: 'center', fontSize: '1.1rem' }}>
            30-Day Listing Activity
          </h3>
          <div style={{ height: '260px' }}>
            <Line
              data={timeSeriesChartData}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                  y: { beginAtZero: true, ticks: { precision: 0 } },
                },
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
};
