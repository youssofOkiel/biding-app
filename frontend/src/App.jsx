import React, { useState, useEffect, useRef } from 'react';
import './App.css';

const WS_URL = process.env.REACT_APP_WS_URL || 
  (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? 'ws://localhost:88/ws/bid' 
    : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/bid`);

function App() {
  const [bidderName, setBidderName] = useState('');
  const [bidAmount, setBidAmount] = useState('');
  const [highestBid, setHighestBid] = useState(null);
  const [bidHistory, setBidHistory] = useState([]);
  const [error, setError] = useState(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);

  useEffect(() => {
    // Connect WebSocket
    const connect = () => {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        setError(null);
      };
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'initial_state') {
            setHighestBid(data.data.highest_bid || { amount: 0, bidder: null, timestamp: null, bid_id: null });
            setBidHistory(data.data.history || []);
          } else if (data.type === 'new_bid' || data.type === 'bid_accepted') {
            const newBid = data.data;
            
            setHighestBid(prev => {
              if (!prev) return newBid;
              const newAmount = parseFloat(newBid.amount);
              const prevAmount = parseFloat(prev.amount || 0);
              return newAmount > prevAmount ? newBid : prev;
            });
            
            setBidHistory(prev => {
              const exists = prev.some(b => b.bid_id === newBid.bid_id);
              if (exists) return prev;
              const updated = [newBid, ...prev];
              return updated.slice(0, 50);
            });
            
            if (data.type === 'bid_accepted') {
              setBidAmount('');
              setError(null);
            }
          } else if (data.type === 'error') {
            setError(data.message);
          }
        } catch (err) {
          console.error('Error parsing message:', err);
        }
      };

      ws.onerror = () => {
        setConnected(false);
      };

      ws.onclose = () => {
        setConnected(false);
        // Simple reconnect after 1 second
        if (wsRef.current === ws) {
          setTimeout(connect, 1000);
        }
      };
    };

    connect();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    setError(null);

    if (!bidderName.trim()) {
      setError('Please enter your name');
      return;
    }

    const amount = parseFloat(bidAmount);
    if (isNaN(amount) || amount <= 0) {
      setError('Please enter a valid bid amount');
      return;
    }

    if (highestBid && amount <= parseFloat(highestBid.amount || 0)) {
      setError(`Bid must be higher than current highest bid ($${parseFloat(highestBid.amount).toFixed(2)})`);
      return;
    }

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'submit_bid',
        bidder: bidderName.trim(),
        amount: amount
      }));
    } else {
      setError('Not connected. Please wait for connection...');
    }
  };

  const formatAmount = (amount) => {
    if (!amount) return '$0.00';
    return `$${parseFloat(amount).toFixed(2)}`;
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'N/A';
    try {
      return new Date(timestamp).toLocaleString();
    } catch {
      return timestamp;
    }
  };

  return (
    <div className="App">
      <header className="app-header">
        <h1>Real-Time Bidding</h1>
        <div className="connection-status">
          {connected ? 'Connected' : 'Disconnected'}
        </div>
      </header>

      <main className="app-main">
        <div className="bidding-section">
          <div className="current-bid-card">
            <h2>Current Highest Bid</h2>
            <div className="highest-bid-amount">
              {formatAmount(highestBid?.amount)}
            </div>
            {highestBid?.bidder && (
              <div className="highest-bidder">
                By: {highestBid.bidder}
              </div>
            )}
          </div>

          <div className="bid-form-card">
            <h2>Place Your Bid</h2>
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label htmlFor="bidderName">Your Name</label>
                <input
                  id="bidderName"
                  type="text"
                  value={bidderName}
                  onChange={(e) => setBidderName(e.target.value)}
                  placeholder="Enter your name"
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="bidAmount">Bid Amount ($)</label>
                <input
                  id="bidAmount"
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={bidAmount}
                  onChange={(e) => setBidAmount(e.target.value)}
                  placeholder="0.00"
                  required
                />
              </div>

              {error && (
                <div className="error-message">{error}</div>
              )}

              <button
                type="submit"
                className="submit-button"
                disabled={!connected}
              >
                Submit Bid
              </button>
            </form>
          </div>
        </div>

        <div className="bid-history">
          <h2>Bid History</h2>
          {bidHistory.length === 0 ? (
            <p className="empty-state">No bids yet. Be the first to bid!</p>
          ) : (
            <div className="bid-list">
              {bidHistory.map((bid) => (
                <div key={bid.bid_id || bid.timestamp} className="bid-item">
                  <div className="bid-header">
                    <span className="bidder-name">{bid.bidder || 'Anonymous'}</span>
                    <span className="bid-amount">{formatAmount(bid.amount)}</span>
                  </div>
                  <div className="bid-timestamp">{formatTimestamp(bid.timestamp)}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
