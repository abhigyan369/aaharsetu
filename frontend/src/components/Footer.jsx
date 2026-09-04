import React from 'react';
import { ExternalLink } from 'lucide-react';
import './Footer.css';

export const Footer = () => {
  return (
    <footer className="app-footer">
      <div className="container">
        <div className="footer-content-wrapper">
          <div className="footer-text-group">
            <p>© {new Date().getFullYear()} AaharSetu Food Waste Redistribution Platform. All rights reserved.</p>
            <p style={{ fontSize: '0.825rem', color: '#9ca3af' }}>
              Connecting surplus food with communities in need.
            </p>
          </div>

          <a
            href="https://www.linkedin.com/in/abhigyan369/"
            target="_blank"
            rel="noopener noreferrer"
            className="developer-badge-link"
            title="View Abhigyan Kumar's LinkedIn Profile"
          >
            <svg className="linkedin-badge-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect width="24" height="24" rx="5" fill="#0A66C2"/>
              <path d="M19 19H16V13.8824C16 12.4353 14.8 11.5294 13.6 11.5294C12.4 11.5294 11.5 12.4353 11.5 13.8824V19H8.5V9.5H11.5V10.8706C12.1 9.88235 13.3 9.25882 14.7 9.25882C17.2 9.25882 19 10.9765 19 14.2353V19Z" fill="white"/>
              <path d="M6.5 7.5C7.32843 7.5 8 6.82843 8 6C8 5.17157 7.32843 4.5 6.5 4.5C5.67157 4.5 5 5.17157 5 6C5 6.82843 5.67157 7.5 6.5 7.5Z" fill="white"/>
              <path d="M5 9.5H8V19H5V9.5Z" fill="white"/>
            </svg>
            <span className="badge-text">
              Developed by <strong>Abhigyan Kumar</strong>
            </span>
            <ExternalLink size={20} className="external-link-icon" />
          </a>
        </div>
      </div>
    </footer>
  );
};

