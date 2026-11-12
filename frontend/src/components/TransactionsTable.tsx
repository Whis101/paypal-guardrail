import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AllCommunityModule,
  ModuleRegistry,
  themeQuartz,
  type ColDef,
  type ValueFormatterParams,
} from 'ag-grid-community'
import { AgGridReact, type CustomCellRendererProps } from 'ag-grid-react'
import { api } from '../api/client'
import { formatDate, formatMoney, statusMeta } from '../format'
import type { Transaction } from '../types'
import PaypalLink from './PaypalLink'
import StatusBadge from './StatusBadge'

ModuleRegistry.registerModules([AllCommunityModule])

const gridTheme = themeQuartz.withParams({
  accentColor: '#0070e0',
  headerBackgroundColor: '#f4f7fb',
  headerFontWeight: 600,
  borderRadius: 8,
  wrapperBorderRadius: 12,
  fontFamily: 'inherit',
  fontSize: 14,
  rowHeight: 52,
  headerHeight: 46,
})

function StatusCell({ value }: CustomCellRendererProps<Transaction, string>) {
  return value ? <StatusBadge status={value} /> : null
}

function PaypalCell({ data }: CustomCellRendererProps<Transaction>) {
  if (!data) return null
  return <PaypalLink orderId={data.paypal_order_id} captureId={data.paypal_capture_id} />
}

export default function TransactionsTable() {
  const [rows, setRows] = useState<Transaction[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [quickFilter, setQuickFilter] = useState('')
  const [loading, setLoading] = useState(false)

  const load = useCallback(() => {
    api
      .transactions()
      .then((t) => {
        setRows(t)
        setError(null)
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false))
  }, [])

  useEffect(load, [load])

  const columnDefs = useMemo<ColDef<Transaction>[]>(
    () => [
      {
        field: 'created_at',
        headerName: 'Time',
        width: 190,
        sort: 'desc',
        filter: 'agDateColumnFilter',
        valueFormatter: (p: ValueFormatterParams<Transaction, string>) => formatDate(p.value),
        filterValueGetter: (p) => (p.data ? new Date(p.data.created_at) : null),
        getQuickFilterText: (p) => formatDate(p.value),
      },
      { field: 'merchant_raw', headerName: 'Merchant', width: 200, filter: 'agTextColumnFilter' },
      { field: 'category', headerName: 'Category', width: 150, filter: 'agTextColumnFilter' },
      {
        field: 'amount_cents',
        headerName: 'Amount',
        width: 130,
        type: 'rightAligned',
        filter: 'agNumberColumnFilter',
        filterValueGetter: (p) => (p.data ? p.data.amount_cents / 100 : null),
        valueFormatter: (p: ValueFormatterParams<Transaction, number>) =>
          formatMoney(p.value, p.data?.currency ?? 'USD'),
        getQuickFilterText: (p) => formatMoney(p.value as number),
      },
      {
        field: 'status',
        headerName: 'Status',
        width: 170,
        filter: 'agTextColumnFilter',
        cellRenderer: StatusCell,
        // filter / quick-filter by the human label as well as the raw enum
        filterValueGetter: (p) => (p.data ? `${statusMeta(p.data.status).label} ${p.data.status}` : ''),
        getQuickFilterText: (p) => `${statusMeta(String(p.value)).label} ${String(p.value)}`,
      },
      {
        field: 'decision_reason',
        headerName: 'Decision reason',
        flex: 1,
        minWidth: 260,
        filter: 'agTextColumnFilter',
        tooltipField: 'decision_reason',
        wrapText: true,
        autoHeight: true,
        cellClass: 'reason-cell',
      },
      {
        field: 'paypal_order_id',
        headerName: 'PayPal order',
        width: 220,
        filter: 'agTextColumnFilter',
        cellRenderer: PaypalCell,
      },
    ],
    [],
  )

  const defaultColDef = useMemo<ColDef<Transaction>>(
    () => ({ sortable: true, resizable: true, floatingFilter: false }),
    [],
  )

  return (
    <div className="stack">
      <div className="toolbar">
        <h2>Transactions</h2>
        <div className="toolbar-right">
          <input
            className="search"
            type="search"
            placeholder="Search merchant, category, status, reason…"
            value={quickFilter}
            onChange={(e) => setQuickFilter(e.target.value)}
          />
          <button
            className="btn"
            onClick={() => {
              setLoading(true)
              load()
            }}
            disabled={loading}
          >
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      <div className="grid-wrap">
        <AgGridReact<Transaction>
          theme={gridTheme}
          rowData={rows}
          columnDefs={columnDefs}
          defaultColDef={defaultColDef}
          getRowId={(p) => String(p.data.id)}
          quickFilterText={quickFilter}
          pagination
          paginationPageSize={20}
          paginationPageSizeSelector={[10, 20, 50, 100]}
          tooltipShowDelay={300}
          enableCellTextSelection
          domLayout="autoHeight"
          overlayNoRowsTemplate="No transactions yet. Run the shopping agent from the Dashboard."
          loading={rows === null && !error}
        />
      </div>
    </div>
  )
}
