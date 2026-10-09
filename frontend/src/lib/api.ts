import { apiBaseUrl } from './env'
import type {
  CorrectionEmailDraft,
  DocumentReview,
  PipelineProgress,
  ReviewUpdate,
} from './types'

export async function getAuthSession(): Promise<boolean> {
  const response = await apiRequest('/api/auth/session')
  const payload: unknown = await response.json()
  if (!isRecord(payload) || typeof payload.authenticated !== 'boolean') {
    throw new Error('The API returned an invalid sign-in status.')
  }
  return payload.authenticated
}

export async function login(name: string, password: string): Promise<void> {
  const response = await apiRequest('/api/auth/login', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ name, password }),
  })
  const payload: unknown = await response.json()
  if (!isRecord(payload) || payload.authenticated !== true) {
    throw new Error('The API did not confirm sign-in.')
  }
}

export async function logout(): Promise<void> {
  const response = await apiRequest('/api/auth/logout', { method: 'POST' })
  const payload: unknown = await response.json()
  if (!isRecord(payload) || payload.authenticated !== false) {
    throw new Error('The API did not confirm sign-out.')
  }
}

export async function processDocument(
  file: File,
  onProgress: (progress: PipelineProgress) => void,
): Promise<DocumentReview> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await apiRequest('/api/documents/progress', {
    method: 'POST',
    body: formData,
  })
  if (!response.headers.get('content-type')?.includes('text/event-stream') || !response.body) {
    throw new Error('The API did not return a document-processing progress stream.')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let review: DocumentReview | null = null
  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const events = buffer.split(/\r?\n\r?\n/)
    buffer = events.pop() ?? ''
    for (const eventText of events) {
      const event = parseProgressEvent(eventText)
      if (event.type === 'progress') onProgress(event.progress)
      if (event.type === 'error') throw new Error(event.message)
      if (event.type === 'result') review = event.review
    }
    if (done) break
  }
  if (buffer.trim()) {
    const event = parseProgressEvent(buffer)
    if (event.type === 'progress') onProgress(event.progress)
    if (event.type === 'error') throw new Error(event.message)
    if (event.type === 'result') review = event.review
  }
  if (!review) throw new Error('The API closed the progress stream without a review result.')
  return review
}

export async function listDocuments(): Promise<DocumentReview[]> {
  const response = await apiRequest('/api/documents')
  const payload: unknown = await response.json()
  if (!Array.isArray(payload) || !payload.every(isDocumentReview)) {
    throw new Error('The API returned an invalid document list.')
  }
  return payload
}

export async function getDocument(reviewId: string): Promise<DocumentReview> {
  return requestReview(`/api/documents/${encodeURIComponent(reviewId)}`)
}

export async function updateDocument(
  reviewId: string,
  update: ReviewUpdate,
): Promise<DocumentReview> {
  return requestReview(`/api/documents/${encodeURIComponent(reviewId)}`, {
    method: 'PATCH',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(update),
  })
}

export async function decideDocument(
  reviewId: string,
  decision: 'approved' | 'rejected',
  reason?: string,
): Promise<DocumentReview> {
  return requestReview(`/api/documents/${encodeURIComponent(reviewId)}/decision`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ decision, reason }),
  })
}

export async function deleteDocument(reviewId: string): Promise<void> {
  await apiRequest(`/api/documents/${encodeURIComponent(reviewId)}`, {
    method: 'DELETE',
  })
}

export async function createCorrectionEmail(
  reviewId: string,
  recipientEmail: string,
): Promise<CorrectionEmailDraft> {
  const response = await apiRequest(
    `/api/documents/${encodeURIComponent(reviewId)}/correction-email`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ recipient_email: recipientEmail }),
    },
  )
  const payload: unknown = await response.json()
  if (
    !isRecord(payload) ||
    typeof payload.to !== 'string' ||
    typeof payload.subject !== 'string' ||
    typeof payload.body !== 'string'
  ) {
    throw new Error('The API returned an invalid correction email draft.')
  }
  return {
    to: payload.to,
    subject: payload.subject,
    body: payload.body,
  }
}

type ProgressEvent =
  | { type: 'progress'; progress: PipelineProgress }
  | { type: 'result'; review: DocumentReview }
  | { type: 'error'; message: string }

function parseProgressEvent(eventText: string): ProgressEvent {
  let eventName = ''
  const data: string[] = []
  for (const line of eventText.split(/\r?\n/)) {
    if (line.startsWith('event:')) eventName = line.slice(6).trim()
    if (line.startsWith('data:')) data.push(line.slice(5).trim())
  }

  let payload: unknown
  try {
    payload = JSON.parse(data.join('\n'))
  } catch {
    throw new Error('The API sent malformed progress data.')
  }
  if (!isRecord(payload)) throw new Error('The API sent an invalid progress event.')
  if (eventName === 'progress' && isPipelineProgress(payload)) {
    return { type: 'progress', progress: payload }
  }
  if (eventName === 'result' && isDocumentReview(payload)) {
    return { type: 'result', review: payload }
  }
  if (eventName === 'error' && typeof payload.message === 'string') {
    return { type: 'error', message: payload.message }
  }
  throw new Error('The API sent an unknown document-processing event.')
}

function isPipelineProgress(value: Record<string, unknown>): value is Record<string, unknown> & PipelineProgress {
  return (
    ['classification', 'extraction', 'validation', 'general_ledger'].includes(String(value.stage)) &&
    (value.status === 'started' || value.status === 'completed')
  )
}

function isDocumentReview(value: unknown): value is DocumentReview {
  if (!isRecord(value) || !isRecord(value.result) || !isRecord(value.result.classification)) {
    return false
  }
  return (
    typeof value.id === 'string' &&
    typeof value.filename === 'string' &&
    ['needs_review', 'ready', 'approved', 'rejected'].includes(String(value.status)) &&
    ['invoice', 'receipt', 'other'].includes(
      String(value.result.classification.document_type),
    ) &&
    typeof value.result.classification.reason === 'string' &&
    Array.isArray(value.result.validation_findings) &&
    Array.isArray(value.result.general_ledger_accounts)
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

async function requestReview(
  path: string,
  init?: RequestInit,
): Promise<DocumentReview> {
  const response = await apiRequest(path, init)
  const payload: unknown = await response.json()
  if (!isDocumentReview(payload)) throw new Error('The API returned an invalid document review.')
  return payload
}

async function apiRequest(path: string, init?: RequestInit): Promise<Response> {
  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}${path}`, init)
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error(
        `Could not reach the API at ${apiBaseUrl}. Make sure the FastAPI server is running.`,
        { cause: error },
      )
    }
    throw error
  }
  if (!response.ok) {
    const detail = await readErrorDetail(response)
    if (response.status === 401 && !path.startsWith('/api/auth/')) {
      window.dispatchEvent(new Event('invoice-review:auth-required'))
    }
    throw new Error(detail || `The API request failed with status ${response.status}.`)
  }
  return response
}

async function readErrorDetail(response: Response): Promise<string | null> {
  try {
    const body: unknown = await response.json()
    if (
      isRecord(body) &&
      typeof body.detail === 'string'
    ) {
      return body.detail
    }
  } catch {
    return null
  }
  return null
}
