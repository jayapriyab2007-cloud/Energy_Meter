import React from 'react'

export default function Pagination({ page, total, pageSize, onPageChange }) {
  const totalPages = Math.ceil(total / pageSize) || 1
  if (totalPages <= 1) return null

  return (
    <div className="row" style={{ marginTop: 12, justifyContent: 'flex-end', gap: 6 }}>
      <button
        className="btn alt"
        style={{ padding: '4px 10px' }}
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        Previous
      </button>
      <span style={{ color: 'var(--mut)', alignSelf: 'center', fontSize: 13 }}>
        Page {page} of {totalPages}
      </span>
      <button
        className="btn alt"
        style={{ padding: '4px 10px' }}
        disabled={page >= totalPages}
        onClick={() => onPageChange(page + 1)}
      >
        Next
      </button>
    </div>
  )
}
