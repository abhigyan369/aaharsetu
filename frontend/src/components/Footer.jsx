import React from 'react';

export const Footer = () => {
  return (
    <footer style={{
      backgroundColor: 'var(--color-surface)',
      borderTop: '1px solid var(--color-border)',
      padding: '2rem 0',
      marginTop: 'auto',
      color: 'var(--color-text-muted)',
      textAlign: 'center',
      fontSize: '0.9rem'
    }}>
      <div className="container">
        <p>© {new Date().getFullYear()} AaharSetu Food Waste Redistribution Platform. All rights reserved.</p>
        <p style={{ marginTop: '0.5rem', fontSize: '0.8rem' }}>
          Connecting surplus food with communities in need.
        </p>
      </div>
    </footer>
  );
};
