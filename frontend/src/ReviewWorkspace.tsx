import { useState } from 'react'
import {
  createCorrectionEmail,
  decideDocument,
  deleteDocument,
  updateDocument,
} from './lib/api'
import type {
  CorrectionEmailDraft,
  DocumentReview,
  Invoice,
  Receipt,
  ReviewUpdate,
  ValidationFinding,
} from './lib/types'

type FinancialDocument = Invoice | Receipt
type FieldKind = 'text' | 'date' | 'number'
interface EditableField {
  name: string
  label: string
  kind: FieldKind
}

const invoiceFields: EditableField[] = [
  { name: 'vendor_name', label: 'Supplier', kind: 'text' },
  { name: 'vendor_vat_id', label: 'Supplier VAT number', kind: 'text' },
  { name: 'customer_name', label: 'Customer', kind: 'text' },
  { name: 'customer_vat_id', label: 'Customer VAT number', kind: 'text' },
  { name: 'invoice_number', label: 'Invoice number', kind: 'text' },
  { name: 'purchase_order', label: 'Purchase order', kind: 'text' },
  { name: 'invoice_date', label: 'Invoice date', kind: 'date' },
  { name: 'due_date', label: 'Due date', kind: 'date' },
  { name: 'currency', label: 'Currency', kind: 'text' },
  { name: 'subtotal', label: 'Subtotal', kind: 'number' },
  { name: 'total_tax', label: 'VAT total', kind: 'number' },
  { name: 'invoice_total', label: 'Invoice total', kind: 'number' },
  { name: 'amount_due', label: 'Remaining amount to pay', kind: 'number' },
]
const receiptFields: EditableField[] = [
  { name: 'merchant_name', label: 'Merchant', kind: 'text' },
  { name: 'merchant_address', label: 'Merchant address', kind: 'text' },
  { name: 'transaction_date', label: 'Transaction date', kind: 'date' },
  { name: 'transaction_time', label: 'Transaction time', kind: 'text' },
  { name: 'receipt_type', label: 'Receipt type', kind: 'text' },
  { name: 'country_region', label: 'Country or region', kind: 'text' },
  { name: 'currency', label: 'Currency', kind: 'text' },
  { name: 'subtotal', label: 'Subtotal', kind: 'number' },
  { name: 'total_tax', label: 'VAT total', kind: 'number' },
  { name: 'tip', label: 'Tip', kind: 'number' },
  { name: 'total', label: 'Receipt total', kind: 'number' },
]

interface Props {
  review: DocumentReview
  onReviewChanged: (review: DocumentReview) => void
  onBackToInbox: () => void
  onUploadAnother: () => void
  onDeleted: () => void
}

export function ReviewWorkspace({
  review,
  onReviewChanged,
  onBackToInbox,
  onUploadAnother,
  onDeleted,
}: Props) {
  const document = review.result.document
  const fields = document
    ? document.document_type === 'invoice'
      ? invoiceFields
      : receiptFields
    : []
  const [values, setValues] = useState<Record<string, string>>(() =>
    document ? readFieldValues(document, fields) : {},
  )
  const [selectedAccount, setSelectedAccount] = useState(
    review.selected_gl_account_code ?? '',
  )
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [rejecting, setRejecting] = useState(false)
  const [rejectionReason, setRejectionReason] = useState('')
  const [correctionOpen, setCorrectionOpen] = useState(false)
  const [approveConfirmation, setApproveConfirmation] = useState(false)

  const isFinal = review.status === 'approved' || review.status === 'rejected'
  const hasBlockingErrors = review.result.validation_findings.some(
    (finding) => finding.severity === 'error',
  )
  const isDirty = document
    ? fields.some((field) => values[field.name] !== stringifyField(document, field.name)) ||
      selectedAccount !== (review.selected_gl_account_code ?? '')
    : false
  const suggestedAccount = review.result.general_ledger_accounts.find(
    (account) => account.code === review.result.general_ledger_suggestion?.account_code,
  )
  const supplierIssues = review.result.validation_findings.some((finding) =>
    [
      'vendor_name',
      'vendor_vat_id',
      'customer_name',
      'customer_vat_id',
      'invoice_number',
      'invoice_date',
      'due_date',
      'purchase_order',
      'currency',
      'subtotal',
      'total_tax',
      'invoice_total',
      'amount_due',
      'merchant_name',
      'transaction_date',
      'total',
    ].includes(finding.field),
  )
  const itemConflict = document?.conflicts.find((conflict) => conflict.field === 'line_items')
  const taxConflict = document?.conflicts.find((conflict) => conflict.field === 'tax_details')
  const otherConflicts = document?.conflicts.filter(
    (conflict) => conflict.field !== 'line_items' && conflict.field !== 'tax_details',
  ) ?? []

  async function saveReview() {
    if (!document || isFinal || busy) return
    setBusy(true)
    setError(null)
    try {
      const fieldsToSave = Object.fromEntries(
        fields
          .filter((field) => values[field.name] !== stringifyField(document, field.name))
          .map((field) => [
            field.name,
            values[field.name] === '' ? null : values[field.name],
          ]),
      )
      const update: ReviewUpdate = {
        fields: fieldsToSave,
        selected_gl_account_code: selectedAccount || null,
      }
      onReviewChanged(await updateDocument(review.id, update))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The review could not be saved.')
    } finally {
      setBusy(false)
    }
  }

  async function confirmDecision(decision: 'approved' | 'rejected', reason?: string) {
    setBusy(true)
    setError(null)
    try {
      let currentReview = review
      if (isDirty && document) {
        const fieldsToSave = Object.fromEntries(
          fields
            .filter((field) => values[field.name] !== stringifyField(document, field.name))
            .map((field) => [
              field.name,
              values[field.name] === '' ? null : values[field.name],
            ]),
        )
        currentReview = await updateDocument(review.id, {
          fields: fieldsToSave,
          selected_gl_account_code: selectedAccount || null,
        })
      }
      if (
        decision === 'approved' &&
        (currentReview.status !== 'ready' ||
          currentReview.result.validation_findings.some((finding) => finding.severity === 'error'))
      ) {
        setApproveConfirmation(false)
        onReviewChanged(currentReview)
        return
      }
      onReviewChanged(await decideDocument(currentReview.id, decision, reason))
      setRejecting(false)
      setApproveConfirmation(false)
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : 'The decision could not be saved.')
    } finally {
      setBusy(false)
    }
  }

  async function removeReview() {
    if (!window.confirm('Delete this review from local history? This cannot be undone.')) return
    setBusy(true)
    setError(null)
    try {
      await deleteDocument(review.id)
      onDeleted()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The review could not be deleted.')
      setBusy(false)
    }
  }

  return (
    <div className="result-view review-workspace">
      <div className="review-navigation">
        <button className="back-link" type="button" onClick={onBackToInbox}>
          ← Review inbox
        </button>
        <button className="text-button" type="button" onClick={onUploadAnother}>
          Upload another document
        </button>
      </div>

      <div className="result-topline">
        <span className="step-label">DOCUMENT REVIEW</span>
        <span className={`review-status ${review.status}`}>{statusLabel(review.status)}</span>
      </div>
      <h2>{document ? 'Review and confirm extracted details' : 'Document needs another look'}</h2>
      <p className="result-filename">{review.filename}</p>
      <div className="classification-note">
        <strong>
          Document type: {review.result.classification.document_type === 'invoice'
            ? 'Invoice'
            : review.result.classification.document_type === 'receipt'
              ? 'Receipt'
              : 'Other'}
        </strong>
        <p>{review.result.classification.reason}</p>
      </div>

      {document ? (
        <>
          <section className="result-section">
            <div className="result-section-heading">
              <h3>Details read from the document</h3>
              <span>EDIT VALUES TO CORRECT THEM</span>
            </div>
            <div className="review-fields">
              {fields.map((field) => (
                <label className="review-field" key={field.name}>
                  <span>{field.label}</span>
                  <input
                    disabled={isFinal || busy}
                    type={field.kind}
                    step={field.kind === 'number' ? '0.01' : undefined}
                    value={values[field.name] ?? ''}
                    onChange={(event) =>
                      setValues((current) => ({
                        ...current,
                        [field.name]: event.currentTarget.value,
                      }))
                    }
                  />
                  <small>{sourceLabel(document, field.name)}</small>
                  {field.name === 'amount_due' && (
                    <small className="amount-due-help">
                      If a balance is shown separately on the invoice, enter it here. Otherwise,
                      leave this blank.
                    </small>
                  )}
                </label>
              ))}
            </div>
            {document.line_items.length > 0 && (
              <ItemsSection
                items={document.line_items}
                currency={document.currency}
                otherRead={itemConflict?.azure_openai_value}
              />
            )}
            {document.tax_details.length > 0 && (
              <TaxDetailsSection
                details={document.tax_details}
                otherRead={taxConflict?.azure_openai_value}
                currency={document.currency}
              />
            )}
            {otherConflicts.length > 0 && (
              <div className="conflict-list">
                <strong>Values to double-check</strong>
                <p>
                  Two readings did not match. The first value is shown in the fields above; compare
                  it with the second reading below.
                </p>
                {otherConflicts.map((conflict) => (
                  <div className="conflict-row" key={conflict.field}>
                    <b>{friendlyFieldName(conflict.field)}</b>
                    <span>
                      <strong>First reading (used)</strong>
                      {displayConflictValue(conflict.document_intelligence_value)}
                    </span>
                    <span>
                      <strong>Other reading</strong>
                      {displayConflictValue(conflict.azure_openai_value)}
                    </span>
                  </div>
                ))}
              </div>
            )}
            {!isFinal && (
              <button
                className="secondary-button save-review-button"
                disabled={!isDirty || busy}
                type="button"
                onClick={() => void saveReview()}
              >
                {busy ? 'Saving…' : 'Save changes and rerun checks'}
              </button>
            )}
          </section>

          <section className="result-section">
            <div className="result-section-heading">
              <h3>Checks before approval</h3>
              <span className={hasBlockingErrors ? 'count-error' : 'count-ok'}>
                {hasBlockingErrors ? 'BLOCKING ISSUES' : 'NO BLOCKING ERRORS'}
              </span>
            </div>
            {review.result.validation_findings.length > 0 ? (
              <ul className="finding-list">
                {review.result.validation_findings.map((finding) => (
                  <FindingRow finding={finding} key={`${finding.code}:${finding.field}`} />
                ))}
              </ul>
            ) : (
              <p className="empty-findings">No policy findings for this document.</p>
            )}
          </section>

          <section className="ledger-card review-ledger-card">
            <div className="ledger-icon">GL</div>
            <div className="review-ledger-copy">
              <span className="step-label">BOOKKEEPING</span>
              {suggestedAccount && (
                <p className="suggestion-note">
                  Suggested account: {suggestedAccount.code} · {suggestedAccount.name}. Confirm or
                  choose another account.
                </p>
              )}
              {review.result.general_ledger_suggestion && (
                <p>{review.result.general_ledger_suggestion.reason}</p>
              )}
              <label className="review-field account-field">
                <span>Account for this expense</span>
                <select
                  disabled={isFinal || busy}
                  value={selectedAccount}
                  onChange={(event) => setSelectedAccount(event.currentTarget.value)}
                >
                  <option value="">Select an account</option>
                  {review.result.general_ledger_accounts.map((account) => (
                    <option key={account.code} value={account.code}>
                      {account.code} · {account.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </section>
        </>
      ) : (
        <div className="unsupported-note">
          The upload was classified as unsupported or uncertain. Review the reason, then reject it
          with an explanation or upload the correct document.
        </div>
      )}

      {review.decision_reason && (
        <div className="decision-reason">
          <strong>Rejection reason</strong>
          <p>{review.decision_reason}</p>
        </div>
      )}

      {error && <p className="error-banner review-error" role="alert">{error}</p>}

      {!isFinal && document && supplierIssues && (
        <button
          className="secondary-button correction-button"
          disabled={busy || isDirty}
          type="button"
          onClick={() => setCorrectionOpen(true)}
        >
          Draft supplier correction email
        </button>
      )}

      {!isFinal && (
        <div className="decision-actions">
          <button
            className="reject-button"
            disabled={busy}
            type="button"
            onClick={() => setRejecting((current) => !current)}
          >
            Reject document
          </button>
          <button
            className="primary-button"
            disabled={
              busy ||
              !selectedAccount ||
              (!isDirty && hasBlockingErrors)
            }
            type="button"
            onClick={() => setApproveConfirmation(true)}
          >
            Pass and approve
          </button>
        </div>
      )}
      {!isFinal && document && (
        <p className="decision-guidance" role="status">
          {isDirty
            ? 'Your changes will be saved and checked before your decision is recorded.'
            : hasBlockingErrors
              ? 'Resolve the blocking finance issues before passing this document. You can still reject it.'
              : !selectedAccount
                ? 'Choose and save an account before passing this document. You can still reject it.'
                : 'Your checks are clear. You can pass or reject this document.'}
        </p>
      )}

      {rejecting && !isFinal && (
        <div className="decision-panel">
          <label className="review-field">
            <span>Reason for rejection (required)</span>
            <textarea
              maxLength={1000}
              value={rejectionReason}
              onChange={(event) => setRejectionReason(event.currentTarget.value)}
            />
          </label>
          <div className="decision-actions">
            <button className="secondary-button" type="button" onClick={() => setRejecting(false)}>
              Cancel
            </button>
            <button
              className="reject-button"
              disabled={busy || !rejectionReason.trim()}
              type="button"
              onClick={() => void confirmDecision('rejected', rejectionReason)}
            >
              {busy ? 'Rejecting…' : 'Confirm rejection'}
            </button>
          </div>
        </div>
      )}

      {approveConfirmation && !isFinal && (
        <div className="decision-panel">
          <strong>Pass and approve this document?</strong>
          <p>
            The app will save any changes, rerun the finance checks, and record your approval only
            if the document passes. Approved reviews cannot be edited.
          </p>
          <div className="decision-actions">
            <button
              className="secondary-button"
              type="button"
              onClick={() => setApproveConfirmation(false)}
            >
              Go back
            </button>
            <button
              className="primary-button"
              disabled={busy}
              type="button"
              onClick={() => void confirmDecision('approved')}
            >
              {busy ? 'Approving…' : 'Confirm pass'}
            </button>
          </div>
        </div>
      )}

      {isFinal && (
        <div className="final-review-actions">
          <button className="secondary-button" disabled={busy} type="button" onClick={() => void removeReview()}>
            Delete from local history
          </button>
          <button className="primary-button" type="button" onClick={onUploadAnother}>
            Review another document
          </button>
        </div>
      )}

      {correctionOpen && (
        <CorrectionEmailDialog
          review={review}
          onClose={() => setCorrectionOpen(false)}
        />
      )}
    </div>
  )
}

function ItemsSection({
  items,
  currency,
  otherRead,
}: {
  items: FinancialDocument['line_items']
  currency: string | null
  otherRead?: string
}) {
  const otherItems = otherRead ? parseLineItems(otherRead) : null
  return (
    <section className="review-detail-section" aria-label="Items billed">
      <h4>Items billed</h4>
      {otherItems ? (
        <div className="comparison-columns">
          <div>
            <h5>Value used</h5>
            <ItemsTable items={items} currency={currency} />
          </div>
          <div>
            <h5>Other reading</h5>
            <ItemsTable items={otherItems} currency={currency} />
          </div>
        </div>
      ) : (
        <ItemsTable items={items} currency={currency} />
      )}
    </section>
  )
}

function ItemsTable({
  items,
  currency,
}: {
  items: FinancialDocument['line_items']
  currency: string | null
}) {
  return (
    <div className="review-table-scroll">
      <table className="review-data-table">
        <thead>
          <tr>
            <th scope="col">Description</th>
            <th scope="col">Quantity</th>
            <th scope="col">Price each</th>
            <th scope="col">Line total</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => (
            <tr key={`${item.description ?? 'item'}-${index}`}>
              <td>{item.description || 'Unlabelled item'}</td>
              <td>{displayQuantity(item.quantity, item.unit)}</td>
              <td>{displayAmount(item.unit_price, currency)}</td>
              <td>
                {displayAmount(
                  ('amount' in item ? item.amount : item.total_price) ?? null,
                  currency,
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TaxDetailsSection({
  details,
  otherRead,
  currency,
}: {
  details: FinancialDocument['tax_details']
  otherRead?: string
  currency: string | null
}) {
  const otherDetails = otherRead ? parseTaxDetails(otherRead) : null
  return (
    <section className="review-detail-section" aria-label="VAT breakdown">
      <h4>VAT breakdown</h4>
      {otherDetails ? (
        <div className="comparison-columns">
          <div>
            <h5>Value used</h5>
            <TaxTable details={details} currency={currency} />
          </div>
          <div>
            <h5>Other reading</h5>
            <TaxTable details={otherDetails} currency={currency} />
          </div>
        </div>
      ) : (
        <TaxTable details={details} currency={currency} />
      )}
    </section>
  )
}

function TaxTable({
  details,
  currency,
}: {
  details: FinancialDocument['tax_details']
  currency: string | null
}) {
  return (
    <div className="review-table-scroll">
      <table className="review-data-table">
        <thead>
          <tr>
            <th scope="col">Tax rate</th>
            <th scope="col">Tax amount</th>
            <th scope="col">Before tax</th>
          </tr>
        </thead>
        <tbody>
          {details.map((detail, index) => (
            <tr key={`${detail.description ?? 'tax'}-${index}`}>
              <td>{detail.description || displayTaxRate(detail.rate)}</td>
              <td>{displayAmount(detail.amount, currency)}</td>
              <td>{displayAmount(detail.net_amount, currency)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function parseJsonArray(value: string): unknown[] | null {
  try {
    const parsed: unknown = JSON.parse(value)
    return Array.isArray(parsed) ? parsed : null
  } catch {
    return null
  }
}

function displayConflictValue(value: string): string {
  try {
    const parsed: unknown = JSON.parse(value)
    if (typeof parsed === 'string' || typeof parsed === 'number') return String(parsed)
    if (parsed === null) return 'Not shown'
  } catch {
    return value
  }
  return value
}

function parseLineItems(value: string): FinancialDocument['line_items'] | null {
  const items = parseJsonArray(value)
  if (!items || !items.every(isRecord)) return null
  return items.map((item) => ({
    description: asStringOrNull(item.description),
    quantity: asNumberOrStringOrNull(item.quantity),
    unit: asStringOrNull(item.unit),
    unit_price: asNumberOrStringOrNull(item.unit_price),
    amount: asNumberOrStringOrNull(item.amount),
    total_price: asNumberOrStringOrNull(item.total_price),
  }))
}

function parseTaxDetails(value: string): FinancialDocument['tax_details'] | null {
  const details = parseJsonArray(value)
  if (!details || !details.every(isRecord)) return null
  return details.map((detail) => ({
    description: asStringOrNull(detail.description),
    rate: asNumberOrStringOrNull(detail.rate),
    amount: asNumberOrStringOrNull(detail.amount),
    net_amount: asNumberOrStringOrNull(detail.net_amount),
  }))
}

function asStringOrNull(value: unknown): string | null {
  return typeof value === 'string' ? value : null
}

function asNumberOrStringOrNull(value: unknown): number | string | null {
  return typeof value === 'number' || typeof value === 'string' ? value : null
}

function displayQuantity(value: number | string | null, unit: string | null): string {
  if (value === null) return '—'
  const quantity = Number(value)
  const formatted = Number.isFinite(quantity)
    ? new Intl.NumberFormat(undefined, { maximumFractionDigits: 3 }).format(quantity)
    : String(value)
  return [formatted, unit].filter(Boolean).join(' ')
}

function displayAmount(value: number | string | null, currency: string | null): string {
  if (value === null) return '—'
  const amount = Number(value)
  const formatted = Number.isFinite(amount)
    ? amount.toFixed(2)
    : String(value)
  return currency ? `${formatted} ${currency}` : formatted
}

function displayTaxRate(value: number | string | null): string {
  if (value === null) return 'Tax'
  const rate = Number(value)
  if (!Number.isFinite(rate)) return String(value)
  return `${rate <= 1 ? rate * 100 : rate}% VAT`
}

function friendlyFieldName(field: string): string {
  const labels: Record<string, string> = {
    amount_due: 'Remaining amount to pay',
    invoice_total: 'Invoice total',
    total_tax: 'VAT total',
    vendor_name: 'Supplier',
    customer_name: 'Customer',
    invoice_date: 'Invoice date',
    due_date: 'Payment due date',
    purchase_order: 'Purchase order',
    currency: 'Currency',
  }
  return labels[field] ?? field.replaceAll('_', ' ')
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function CorrectionEmailDialog({
  review,
  onClose,
}: {
  review: DocumentReview
  onClose: () => void
}) {
  const [recipient, setRecipient] = useState('')
  const [draft, setDraft] = useState<CorrectionEmailDraft | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState(false)

  async function generate() {
    setBusy(true)
    setError(null)
    try {
      setDraft(await createCorrectionEmail(review.id, recipient.trim()))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The draft could not be generated.')
    } finally {
      setBusy(false)
    }
  }

  async function copyDraft() {
    if (!draft) return
    try {
      await navigator.clipboard.writeText(
        `To: ${draft.to}\nSubject: ${draft.subject}\n\n${draft.body}`,
      )
      setCopied(true)
    } catch {
      setError('Could not copy to the clipboard. You can select and copy the draft text.')
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section aria-labelledby="correction-title" aria-modal="true" className="correction-dialog" role="dialog">
        <div className="result-section-heading">
          <h3 id="correction-title">Supplier correction draft</h3>
          <button className="text-button" type="button" onClick={onClose}>Close</button>
        </div>
        <p>This creates a draft only. The app will not send an email.</p>
        <label className="review-field">
          <span>Supplier email address</span>
          <input
            autoComplete="email"
            type="email"
            value={recipient}
            onChange={(event) => setRecipient(event.currentTarget.value)}
          />
        </label>
        <button
          className="primary-button"
          disabled={busy || !recipient.trim()}
          type="button"
          onClick={() => void generate()}
        >
          {busy ? 'Drafting…' : 'Generate correction draft'}
        </button>
        {error && <p className="error-banner review-error" role="alert">{error}</p>}
        {draft && (
          <div className="draft-preview">
            <p><strong>To:</strong> {draft.to}</p>
            <p><strong>Subject:</strong> {draft.subject}</p>
            <pre>{draft.body}</pre>
            <button className="secondary-button" type="button" onClick={() => void copyDraft()}>
              {copied ? 'Copied' : 'Copy email'}
            </button>
          </div>
        )}
      </section>
    </div>
  )
}

function readFieldValues(
  document: FinancialDocument,
  fields: EditableField[],
): Record<string, string> {
  return Object.fromEntries(
    fields.map((field) => [field.name, stringifyField(document, field.name)]),
  )
}

function stringifyField(document: FinancialDocument, name: string): string {
  const value = document[name as keyof FinancialDocument]
  return value === null || value === undefined ? '' : String(value)
}

function sourceLabel(document: FinancialDocument, name: string): string {
  const source = document.field_provenance[name]?.source
  if (source === 'document_intelligence') return 'Read from the document'
  if (source === 'azure_openai') return 'Filled from a second reading'
  if (source === 'human') return 'Edited by you'
  if (source === 'missing') return 'Not found on the document'
  return 'Read from the document'
}

function statusLabel(status: DocumentReview['status']): string {
  if (status === 'needs_review') return 'Needs review'
  if (status === 'ready') return 'Ready for decision'
  return status === 'approved' ? 'Passed' : 'Rejected'
}

function FindingRow({ finding }: { finding: ValidationFinding }) {
  return (
    <li className={`finding-row ${finding.severity}`}>
      <span className="finding-indicator">{finding.severity === 'error' ? '!' : 'i'}</span>
      <span>
        <strong>{finding.field.replaceAll('_', ' ')}</strong>
        <small>{finding.message}</small>
      </span>
      <span className="finding-severity">
        {finding.severity === 'error' ? 'Needs fixing' : 'Check'}
      </span>
    </li>
  )
}
