import React, { useState } from 'react';
import { API_URL } from '../config';

interface EmailLoginProps {
  onLoginSuccess: () => void;
}

const EmailLogin: React.FC<EmailLoginProps> = ({ onLoginSuccess }) => {
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [error, setError] = useState('');
  const [otpSent, setOtpSent] = useState(false);

  const handleSendOTP = async () => {
    try {
      const response = await fetch(`${API_URL}/auth/send-otp`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email }),
      });

      const data = await response.json();
      if (response.ok) {
        setOtpSent(true);
        setError('');
      } else {
        setError(data.detail || 'Failed to send OTP');
      }
    } catch (error) {
      setError('Failed to send OTP');
    }
  };

  const handleVerifyOTP = async () => {
    try {
      const response = await fetch(`${API_URL}/auth/verify-otp`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          otp,
        }),
      });

      const data = await response.json();
      if (response.ok) {
        localStorage.setItem('user', JSON.stringify(data.user));
        localStorage.setItem('userId', data.user.id);
        onLoginSuccess();
      } else {
        setError(data.detail || 'Failed to verify OTP');
      }
    } catch (error) {
      setError('Failed to verify OTP');
    }
  };

  return (
    <div className="email-login">
      <h2>Login with Email</h2>
      {error && <div className="error">{error}</div>}
      <div>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Enter your email"
          disabled={otpSent}
        />
        {!otpSent ? (
          <button onClick={handleSendOTP}>Send OTP</button>
        ) : (
          <>
            <input
              type="text"
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
              placeholder="Enter OTP"
            />
            <button onClick={handleVerifyOTP}>Verify OTP</button>
          </>
        )}
      </div>
    </div>
  );
};

export default EmailLogin; 