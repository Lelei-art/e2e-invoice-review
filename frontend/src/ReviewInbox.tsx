import { useEffect, useState } from 'react'
import { deleteDocument, listDocuments } from './lib/api'
import type { DocumentReview } from './lib/types'

interface Props {
  onSelect: (review: DocumentReview) => void
  onUploadAnother: () => void
}

export function ReviewInbox({ onSelect, onUploadAnother }: Props) {
  const [reviews, setReviews] = useState<DocumentReview[]>([])
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let active = true
    listDocuments()
      .then((loadedReviews) => {
        if (active) setReviews(loadedReviews)
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(
            reason instanceof Error ? reason.message : 'The review inbox could not be loaded.',
          )
        }
      })
      .finally(() => {
        if (active) setBusy(false)
      })
    return () => {
      active = false
    }
  }, [reload])

  async function remove(review: DocumentReview) {
    if (!window.confirm(`Delete ${review.filename} from local review history?`)) return
    setError(null)
    try {
      await deleteDocument(review.id)
      setReviews((current) => current.filter((item) => item.id !== review.id))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The review could not be deleted.')
    }
  }

  return (
    <section aria-label="Review inbox" className="inbox-view">
      <div className="inbox-heading">
        <div>
          <span className="step-label">MAYA’S WORKSPACE</span>
          <h2>Review inbox</h2>
          <p>Open a document to correct its details, resolve findings, and record a decision.</p>
        </div>
        <button className="primary-button" type="button" onClick={onUploadAnother}>
          Upload a document
        </button>
      </div>
      {error && <p className="error-banner review-error" role="alert">{error}</p>}
      {error && (
        <button
          className="secondary-button inbox-retry"
          type="button"
          onClick={() => {
            setBusy(true)
            setReload((current) => current + 1)
          }}
        >
          Retry loading reviews
        </button>
      )}
      {busy ? (
        <p className="inbox-empty">Loading saved reviews…</p>
      ) : reviews.length === 0 ? (
        <div className="inbox-empty">
          <strong>No processed documents yet</strong>
          <p>Upload a PDF, PNG, or JPEG to create the first review.</p>
        </div>
      ) : (
        <div className="inbox-list">
          {reviews.map((review) => (
            <article className="inbox-row" key={review.id}>
              <div className="inbox-document-icon">
                {review.result.classification.document_type === 'other'
                  ? 'DOC'
                  : review.result.classification.document_type === 'invoice'
                    ? 'INV'
                    : 'REC'}
              </div>
              <div className="inbox-main">
                <strong>{displayName(review)}</strong>
                <span>{review.filename}</span>
                <small>
                  {new Date(review.created_at).toLocaleString()} ·{' '}
                  {review.result.validation_findings.length === 0
                    ? 'No findings'
                    : `${review.result.validation_findings.length} finding(s)`}
                </small>
              </div>
              <span className={`review-status ${review.status}`}>{statusLabel(review.status)}</span>
              <button
                className="secondary-button inbox-open"
                type="button"
                onClick={() => onSelect(review)}
              >
                Open review
              </button>
              <button
                aria-label={`Delete ${review.filename}`}
                className="inbox-delete"
                type="button"
                onClick={() => void remove(review)}
              >
                Delete
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

function displayName(review: DocumentReview): string {
  const document = review.result.document
  if (!document) return 'Unrecognized document'
  if (document.document_type === 'invoice') {
    return document.vendor_name || 'Invoice supplier not extracted'
  }
  return document.merchant_name || 'Receipt merchant not extracted'
}

function statusLabel(status: DocumentReview['status']): string {
  if (status === 'needs_review') return 'Needs review'
  if (status === 'ready') return 'Ready'
  return status === 'approved' ? 'Passed' : 'Rejected'
}
