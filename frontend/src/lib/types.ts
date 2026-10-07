export type DocumentClassificationType = 'invoice' | 'receipt' | 'other'
export type ValidationSeverity = 'error' | 'warning'
export type PipelineStageName = 'classification' | 'extraction' | 'validation' | 'general_ledger'
export type PipelineStageStatus = 'started' | 'completed'

export interface PipelineProgress {
  stage: PipelineStageName
  status: PipelineStageStatus
}

export interface DocumentClassification {
  document_type: DocumentClassificationType
  reason: string
}

export interface ValidationFinding {
  code: string
  field: string
  severity: ValidationSeverity
  message: string
}

export interface FieldProvenance {
  source: 'document_intelligence' | 'azure_openai' | 'human' | 'missing'
}

export interface ExtractionConflict {
  field: string
  document_intelligence_value: string
  azure_openai_value: string
}

export interface GeneralLedgerAccount {
  code: string
  name: string
  description: string
}

export interface GeneralLedgerSuggestion {
  account_code: string
  reason: string
}

interface FinancialDocument {
  currency: string | null
  subtotal: number | string | null
  total_tax: number | string | null
  line_items: LineItem[]
  tax_details: TaxDetail[]
  field_confidence: Record<string, number>
  field_provenance: Record<string, FieldProvenance>
  conflicts: ExtractionConflict[]
}

export interface LineItem {
  description: string | null
  quantity: number | string | null
  unit: string | null
  unit_price: number | string | null
  amount?: number | string | null
  total_price?: number | string | null
}

export interface TaxDetail {
  description: string | null
  rate: number | string | null
  amount: number | string | null
  net_amount: number | string | null
}

export interface Invoice extends FinancialDocument {
  document_type: 'invoice'
  source_model: 'prebuilt-invoice'
  invoice_number: string | null
  invoice_date: string | null
  due_date: string | null
  purchase_order: string | null
  vendor_name: string | null
  vendor_address: string | null
  vendor_vat_id: string | null
  customer_name: string | null
  customer_address: string | null
  customer_vat_id: string | null
  invoice_total: number | string | null
  amount_due: number | string | null
}

export interface Receipt extends FinancialDocument {
  document_type: 'receipt'
  source_model: 'prebuilt-receipt'
  merchant_name: string | null
  merchant_address: string | null
  merchant_phone_number: string | null
  receipt_type: string | null
  country_region: string | null
  transaction_date: string | null
  transaction_time: string | null
  tip: number | string | null
  total: number | string | null
}

export interface ProcessingResult {
  classification: DocumentClassification
  document: Invoice | Receipt | null
  general_ledger_accounts: GeneralLedgerAccount[]
  general_ledger_suggestion: GeneralLedgerSuggestion | null
  validation_findings: ValidationFinding[]
}

export type ReviewStatus = 'needs_review' | 'ready' | 'approved' | 'rejected'

export interface DocumentReview {
  id: string
  filename: string
  status: ReviewStatus
  result: ProcessingResult
  selected_gl_account_code: string | null
  decision_reason: string | null
  created_at: string
  updated_at: string
}

export interface ReviewUpdate {
  fields: Record<string, string | number | null>
  selected_gl_account_code?: string | null
}

export interface CorrectionEmailDraft {
  to: string
  subject: string
  body: string
}
