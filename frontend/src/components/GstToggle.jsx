import React from 'react';

export const GstToggle = ({ checked, onChange, testId = 'gst-toggle', gstin }) => (
  <label className={`gst-toggle ${checked ? 'on' : ''}`} data-testid={`${testId}-label`}>
    <span className="gst-toggle-text">
      <strong>Add GST (18%)</strong>
      <small>{checked ? `Tax invoice · GSTIN ${gstin || '27CHXPC0935Q2ZK'}` : 'Off — estimate / cash memo, no tax lines'}</small>
    </span>
    <span className="switch">
      <input type="checkbox" role="switch" aria-checked={checked} checked={checked} onChange={e => onChange(e.target.checked)} data-testid={testId} />
      <span />
    </span>
  </label>
);
