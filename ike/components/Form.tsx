import React, { useState } from 'react';

export default function Form() {
  const [channelId, setChannelId] = useState('');
  const [brief, setBrief] = useState('');
  const [runId, setRunId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/api/runPipeline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channelId, brief: brief.trim() ? brief : undefined }),
      });
      const data = await res.json();
      if (res.ok) {
        setRunId(data.runId);
      } else {
        setError(data.error || 'Unknown error');
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  if (runId) {
    // redirect to result page
    window.location.href = `/result/${runId}`;
    return null;
  }

  return (
    <form className="glass-card" onSubmit={handleSubmit} style={{ maxWidth: '500px', margin: 'auto' }}>
      <h2 style={{ marginBottom: '1rem' }}>Создать сценарий</h2>
      <div style={{ marginBottom: '0.75rem' }}>
        <label>Channel ID (или URL)</label>
        <input
          type="text"
          required
          value={channelId}
          onChange={(e) => setChannelId(e.target.value)}
          className="glass-card"
          style={{ width: '100%', padding: '0.5rem' }}
        />
      </div>
      <div style={{ marginBottom: '0.75rem' }}>
        <label>Бриф (необязательно)</label>
        <textarea
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          rows={4}
          className="glass-card"
          style={{ width: '100%', padding: '0.5rem' }}
        />
      </div>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      <button type="submit" disabled={loading} className="glass-card" style={{ width: '100%', padding: '0.75rem', background: 'var(--color-accent)', color: '#fff' }}>
        {loading ? <span className="spinner" /> : 'Запустить'}
      </button>
    </form>
  );
}
