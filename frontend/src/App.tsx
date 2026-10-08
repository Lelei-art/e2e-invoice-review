import { useEffect, useRef, useState, type FormEvent } from 'react'
import { getAuthSession, getDocument, login, logout, processDocument } from './lib/api'
import { ReviewInbox } from './ReviewInbox'
import { ReviewWorkspace } from './ReviewWorkspace'
import type { DocumentReview, PipelineProgress, PipelineStageName } from './lib/types'

const maximumFileSize = 4 * 1024 * 1024
const allowedExtensions = ['.pdf', '.png', '.jpg', '.jpeg']
const pipelineStages: Array<{ name: PipelineStageName; title: string; detail: string }> = [
  { name: 'classification', title: 'Classify document', detail: 'Identify invoice or receipt' },
  { name: 'extraction', title: 'Extract document fields', detail: 'Read the financial details' },
  { name: 'validation', title: 'Validate VAT and policy', detail: 'Check required fields and totals' },
  { name: 'general_ledger', title: 'Suggest GL account', detail: 'Choose from Apex Facilities’ catalog' },
]
type VisibleStageStatus = 'pending' | 'in_progress' | 'completed' | 'failed'
type PipelineStageStates = Record<PipelineStageName, VisibleStageStatus>

function createInitialStageStates(): PipelineStageStates {
  return {
    classification: 'pending',
    extraction: 'pending',
    validation: 'pending',
    general_ledger: 'pending',
  }
}

function App() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [authState, setAuthState] = useState<'checking' | 'signedIn' | 'signedOut' | 'unavailable'>('checking')
  const [password, setPassword] = useState('')
  const [authError, setAuthError] = useState<string | null>(null)
  const [authBusy, setAuthBusy] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [review, setReview] = useState<DocumentReview | null>(null)
  const [screen, setScreen] = useState<'upload' | 'inbox' | 'review'>('upload')
  const [error, setError] = useState<string | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [processingError, setProcessingError] = useState<string | null>(null)
  const [stageStates, setStageStates] = useState<PipelineStageStates>(createInitialStageStates)

  useEffect(() => {
    const handleAuthRequired = () => {
      setAuthState('signedOut')
      setAuthError('Your sign-in expired. Enter the shared password to continue.')
    }
    window.addEventListener('invoice-review:auth-required', handleAuthRequired)
    void getAuthSession()
      .then((authenticated) => setAuthState(authenticated ? 'signedIn' : 'signedOut'))
      .catch((reason: unknown) => {
        setAuthError(reason instanceof Error ? reason.message : 'Could not check sign-in status.')
        setAuthState('unavailable')
      })
    return () => window.removeEventListener('invoice-review:auth-required', handleAuthRequired)
  }, [])

  async function submitLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (authBusy) return
    setAuthBusy(true)
    setAuthError(null)
    try {
      await login(password)
      setPassword('')
      setAuthState('signedIn')
    } catch (reason) {
      setAuthError(reason instanceof Error ? reason.message : 'Sign-in failed.')
    } finally {
      setAuthBusy(false)
    }
  }

  async function signOut() {
    setAuthBusy(true)
    try {
      await logout()
      setAuthState('signedOut')
      setAuthError(null)
    } catch (reason) {
      setAuthError(reason instanceof Error ? reason.message : 'Sign-out failed.')
    } finally {
      setAuthBusy(false)
    }
  }

  function openFilePicker() {
    if (inputRef.current) inputRef.current.value = ''
    inputRef.current?.click()
  }

  function selectFile(candidate: File | undefined) {
    if (!candidate) return
    setReview(null)
    setScreen('upload')
    setError(null)
    setProcessingError(null)
    const extension = getExtension(candidate.name)
    if (!allowedExtensions.includes(extension)) {
      setFile(null)
      setError('Choose a PDF, PNG, or JPEG document.')
      return
    }
    if (candidate.size === 0) {
      setFile(null)
      setError('That file is empty. Choose a document with content.')
      return
    }
    if (candidate.size > maximumFileSize) {
      setFile(null)
      setError('This demo accepts files up to 4 MB.')
      return
    }
    setFile(candidate)
  }

  async function startProcessing() {
    if (!file || isProcessing) return
    setIsProcessing(true)
    setError(null)
    setProcessingError(null)
    setReview(null)
    setStageStates(createInitialStageStates())
    try {
      const processedReview = await processDocument(file, (progress) => {
        setStageStates((current) => updateStageStates(current, progress))
      })
      setReview(processedReview)
      setScreen('review')
    } catch (reason) {
      setProcessingError(
        reason instanceof Error ? reason.message : 'The document could not be processed.',
      )
      setStageStates((current) => {
        const activeStage = pipelineStages.find((stage) => current[stage.name] === 'in_progress')
        return activeStage
          ? { ...current, [activeStage.name]: 'failed' }
          : current
      })
    } finally {
      setIsProcessing(false)
    }
  }

  function reset() {
    setReview(null)
    setFile(null)
    setScreen('upload')
    setError(null)
    setProcessingError(null)
    setStageStates(createInitialStageStates())
    if (inputRef.current) inputRef.current.value = ''
  }

  async function openReview(reviewId: string) {
    try {
      setReview(await getDocument(reviewId))
      setScreen('review')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The review could not be loaded.')
      setScreen('inbox')
    }
  }

  if (authState !== 'signedIn') {
    return (
      <main className="auth-shell">
        <section className="auth-card" aria-labelledby="auth-title">
          <span className="brand-mark" aria-hidden="true">A</span>
          <p className="auth-eyebrow">APEX FACILITIES B.V.</p>
          <h1 id="auth-title">
            {authState === 'checking' ? 'Checking access' : 'Shared workspace'}
          </h1>
          {authState === 'checking' ? (
            <p className="auth-description">Checking your sign-in status…</p>
          ) : authState === 'unavailable' ? (
            <>
              <p className="auth-description">The sign-in service could not be reached.</p>
              {authError && <p className="error-banner" role="alert">{authError}</p>}
              <button className="auth-submit" type="button" onClick={() => window.location.reload()}>
                Try again
              </button>
            </>
          ) : (
            <>
              <p className="auth-description">Enter the shared password to access invoice reviews.</p>
              <form className="auth-form" onSubmit={(event) => void submitLogin(event)}>
                <label htmlFor="shared-password">Shared password</label>
                <input
                  autoComplete="current-password"
                  id="shared-password"
                  onChange={(event) => setPassword(event.target.value)}
                  required
                  type="password"
                  value={password}
                />
                {authError && <p className="error-banner" role="alert">{authError}</p>}
                <button className="auth-submit" disabled={authBusy} type="submit">
                  {authBusy ? 'Signing in…' : 'Sign in'}
                </button>
              </form>
            </>
          )}
        </section>
      </main>
    )
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a aria-label="Apex Facilities document review home" className="brand" href="/">
          <span className="brand-mark" aria-hidden="true">N</span>
          <span className="brand-copy">
            <strong>apex</strong>
            <span>FACILITIES B.V.</span>
          </span>
        </a>
        <nav aria-label="Main navigation" className="workspace-nav">
          <button
            className={screen === 'upload' ? 'active' : ''}
            type="button"
            onClick={reset}
          >
            Upload
          </button>
          <button
            className={screen === 'inbox' ? 'active' : ''}
            type="button"
            onClick={() => {
              setError(null)
              setScreen('inbox')
            }}
          >
            Review inbox
          </button>
          <button disabled={authBusy} type="button" onClick={() => void signOut()}>
            Sign out
          </button>
        </nav>
      </header>

      <main className="page-content">
        <div className="eyebrow"><span /> FINANCE OPERATIONS <span /></div>
        <section className="intro">
          <h1>Make every document<br /><em>ready for review.</em></h1>
          <p>
            Bring an invoice or receipt into focus. We’ll extract the details, check the rules,
            and prepare a general ledger suggestion.
          </p>
        </section>

        {screen === 'inbox' ? (
          <section className="work-card">
            {error && <p className="error-banner review-error" role="alert">{error}</p>}
            <ReviewInbox
              onSelect={(selectedReview) => void openReview(selectedReview.id)}
              onUploadAnother={reset}
            />
          </section>
        ) : screen === 'review' && review ? (
          <section className="work-card">
            <ReviewWorkspace
              key={`${review.id}:${review.updated_at}`}
              review={review}
              onReviewChanged={setReview}
              onBackToInbox={() => setScreen('inbox')}
              onUploadAnother={reset}
              onDeleted={() => {
                setReview(null)
                setScreen('inbox')
              }}
            />
          </section>
        ) : (
          <section aria-label="Document review" className="work-card">
            {isProcessing || processingError ? (
            <ProcessingState
              filename={file?.name ?? 'Document'}
              error={processingError}
              stageStates={stageStates}
              onRetry={() => void startProcessing()}
              onChoose={openFilePicker}
            />
          ) : file ? (
            <DocumentConfirmation
              file={file}
              error={error}
              onChoose={openFilePicker}
              onStart={() => void startProcessing()}
            />
          ) : (
            <>
              <div className="card-heading">
                <div>
                  <span className="step-label">YOUR NEXT STEP</span>
                  <h2>Choose a document to begin</h2>
                </div>
                <span className="secure-note"><LockIcon /> Stays in your review</span>
              </div>

              <button
                className="drop-area"
                type="button"
                onClick={openFilePicker}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault()
                  selectFile(event.dataTransfer.files[0])
                }}
              >
                <span className="upload-icon"><UploadIcon /></span>
                <strong>Drop your invoice or receipt here</strong>
                <span className="drop-help">or <span className="browse-link">browse files</span></span>
                <span className="file-rules">PDF, PNG, JPG or JPEG <i /> Up to 4 MB</span>
              </button>

              {error && <p className="error-banner" role="alert">{error}</p>}

              <div className="pipeline-preview">
                <span className="pipeline-label">YOUR DOCUMENT WILL BE</span>
                <div className="pipeline-steps">
                  <PipelineStep number="01" title="Classified" detail="Invoice or receipt" />
                  <span className="step-connector" />
                  <PipelineStep number="02" title="Checked" detail="Fields & finance rules" />
                  <span className="step-connector" />
                  <PipelineStep number="03" title="Categorized" detail="Ledger suggestion" />
                </div>
              </div>

            </>
            )}
          </section>
        )}

        {screen === 'upload' && (
          <p className="privacy-note">
            <LockIcon /> Documents are processed by your configured review services. The original
            upload is not kept by this API.
          </p>
        )}
        <input
          ref={inputRef}
          accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
          className="visually-hidden"
          type="file"
          onChange={(event) => selectFile(event.currentTarget.files?.[0])}
        />
      </main>
      <footer className="page-footer">
        <span>Apex Facilities B.V. <i /> Document review</span>
        <span>Internal finance workspace</span>
      </footer>
    </div>
  )
}

function PipelineStep({ number, title, detail }: { number: string; title: string; detail: string }) {
  return (
    <div className="pipeline-step">
      <span className="pipeline-number">{number}</span>
      <span><strong>{title}</strong><small>{detail}</small></span>
    </div>
  )
}

function DocumentConfirmation({
  file,
  error,
  onChoose,
  onStart,
}: {
  file: File
  error: string | null
  onChoose: () => void
  onStart: () => void
}) {
  return (
    <div className="confirmation-view">
      <div className="confirmation-heading">
        <button className="back-link" type="button" onClick={onChoose}>← Choose a different document</button>
        <div className="confirmation-title">
          <span className="step-label">STEP 2 OF 2 · CONFIRM BEFORE PROCESSING</span>
          <h2>Is this the right document?</h2>
          <p>Check the preview below. Your file is only sent for review when you start the process.</p>
        </div>
      </div>

      <FilePreview file={file} />

      <div className="confirmation-file">
        <span className="file-type-icon">{getExtension(file.name) === '.pdf' ? 'PDF' : 'IMG'}</span>
        <span className="selected-file-info">
          <strong>{file.name}</strong>
          <small>{formatFileSize(file.size)} <i /> Ready to review</small>
        </span>
        <span className="confirmation-check"><CheckIcon /> Selected</span>
      </div>

      {error && <p className="error-banner confirmation-error" role="alert">{error}</p>}

      <div className="confirmation-actions">
        <button className="secondary-button" type="button" onClick={onChoose}>Change document</button>
        <button className="primary-button" type="button" onClick={onStart}>
          Start document review <ArrowIcon />
        </button>
      </div>
      <p className="confirmation-note"><LockIcon /> Nothing is sent until you click “Start document review”.</p>
    </div>
  )
}

function FilePreview({ file }: { file: File }) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const isPdf = getExtension(file.name) === '.pdf'

  useEffect(() => {
    const url = URL.createObjectURL(file)
    let isCurrent = true
    queueMicrotask(() => {
      if (isCurrent) setPreviewUrl(url)
    })
    return () => {
      isCurrent = false
      URL.revokeObjectURL(url)
    }
  }, [file])

  return (
    <div className={`document-preview ${isPdf ? 'pdf-preview' : 'image-file-preview'}`}>
      {previewUrl ? (
        isPdf ? (
          <iframe title={`Preview of ${file.name}`} src={previewUrl} />
        ) : (
          <img src={previewUrl} alt={`Preview of ${file.name}`} />
        )
      ) : (
        <span>Loading document preview…</span>
      )}
    </div>
  )
}

function CheckIcon() {
  return <svg aria-hidden="true" viewBox="0 0 16 16"><path d="m3.5 8.2 2.8 2.7 6.2-6" /></svg>
}

function updateStageStates(
  current: PipelineStageStates,
  progress: PipelineProgress,
): PipelineStageStates {
  return {
    ...current,
    [progress.stage]: progress.status === 'started' ? 'in_progress' : 'completed',
  }
}

function ProcessingState({
  filename,
  error,
  stageStates,
  onRetry,
  onChoose,
}: {
  filename: string
  error: string | null
  stageStates: PipelineStageStates
  onRetry: () => void
  onChoose: () => void
}) {
  return (
    <div aria-live="polite" className="processing-state">
      {!error && <span className="processing-spinner" />}
      <span className="step-label">{error ? 'REVIEW NEEDS ATTENTION' : 'REVIEW IN PROGRESS'}</span>
      <h2>{error ? 'We couldn’t finish this review' : 'Reviewing your document'}</h2>
      <p className="processing-filename">{filename}</p>
      <ol className="processing-steps">
        {pipelineStages.map((stage, index) => (
          <li className={`processing-step ${stageStates[stage.name]}`} key={stage.name}>
            <span className="processing-step-marker">
              {stageStates[stage.name] === 'completed' ? <CheckIcon /> : index + 1}
            </span>
            <span className="processing-step-copy">
              <strong>{stage.title}</strong>
              <small>{stage.detail}</small>
            </span>
            <span className="processing-step-status">
              {stageStates[stage.name] === 'completed' && 'Done'}
              {stageStates[stage.name] === 'in_progress' && 'In progress'}
              {stageStates[stage.name] === 'failed' && 'Failed'}
            </span>
          </li>
        ))}
      </ol>
      {error ? (
        <>
          <p className="processing-error" role="alert">{error}</p>
          <div className="processing-actions">
            <button className="secondary-button" type="button" onClick={onChoose}>Choose another file</button>
            <button className="primary-button" type="button" onClick={onRetry}>Try again</button>
          </div>
        </>
      ) : (
        <p className="processing-hint">Each step updates as the backend completes it. This can take a little while.</p>
      )}
    </div>
  )
}

function getExtension(filename: string): string {
  const separator = filename.lastIndexOf('.')
  return separator >= 0 ? filename.slice(separator).toLowerCase() : ''
}

function formatFileSize(bytes: number): string {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function UploadIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5M5 15v4h14v-4" /></svg>
}

function ArrowIcon() {
  return <svg aria-hidden="true" className="arrow-icon" viewBox="0 0 20 20"><path d="M4 10h12m-5-5 5 5-5 5" /></svg>
}

function LockIcon() {
  return <svg aria-hidden="true" className="lock-icon" viewBox="0 0 16 16"><rect x="3.25" y="7" width="9.5" height="7" rx="1.5" /><path d="M5.5 7V4.75a2.5 2.5 0 0 1 5 0V7" /></svg>
}

export default App
