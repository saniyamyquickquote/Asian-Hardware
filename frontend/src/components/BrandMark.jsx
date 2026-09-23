import React from 'react';

export const BrandMark = ({ compact = false, testId = 'brand-lockup' }) => <div className={`brand-lockup ${compact ? 'compact' : ''}`} data-testid={testId}>
  <span className="brand-icon" aria-hidden="true"><span className="brand-roof" /><span className="brand-stripes"><i /><i /><i /><i /></span></span>
  {!compact && <span className="brand-words">ASIAN <strong>HARDWARE</strong><small>AND PAINTS · NASHIK</small></span>}
</div>;