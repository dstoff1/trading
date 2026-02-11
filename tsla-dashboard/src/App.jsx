import { useEffect, useState } from 'react'
import './App.css'
import PriceChart from './PriceChart.jsx'

const API_URL = 'http://localhost:5000/api/tsla'

function formatNumber(value, options = {}) {
  if (value == null || Number.isNaN(value)) return '—'
  return new Intl.NumberFormat('en-US', options).format(value)
}

function App() {
  const [quote, setQuote] = useState(null)
  const [history, setHistory] = useState([])
  const [error, setError] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [currentTail, setCurrentTail] = useState(null)
  const [sessionContext, setSessionContext] = useState(null)

  useEffect(() => {
    let cancelled = false

    const fetchQuote = async () => {
      try {
        const res = await fetch(API_URL)
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`)
        }
        const data = await res.json()

        if (cancelled) return

        const price = Number(data.price)
        const high = Number(data.high)
        const low = Number(data.low)
        const volume = Number(data.volume)
        const bars = Array.isArray(data.bars) ? data.bars : []

        setQuote({
          price,
          high,
          low,
          volume,
          timestamp: data.timestamp,
        })

        setHistory(bars)

        const tail = data.current_tail
        if (tail && tail.type) {
          setCurrentTail(tail)
        } else {
          setCurrentTail(null)
        }

        setSessionContext({
          current_tail_opportunity: data.current_tail_opportunity,
          session_stats: data.session_stats,
          initial_balance: data.initial_balance,
          extensions: data.extensions,
          previous_session: data.previous_session,
        })

        setError(null)
        setLastUpdated(new Date())
      } catch (err) {
        if (cancelled) return
        setError(err.message || 'Failed to fetch TSLA data')
      }
    }

    fetchQuote()
    const id = setInterval(fetchQuote, 5000)

    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  const statusLabel = error
    ? 'Disconnected'
    : quote
      ? 'Live from yfinance'
      : 'Connecting…'

  const lastUpdatedLabel = lastUpdated
    ? lastUpdated.toLocaleTimeString()
    : '—'

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <div className="app-title">TSLA Live Tape</div>
          <div className="app-subtitle">
            Streaming snapshot from your local Flask proxy every second
          </div>
        </div>
        <span className="badge">Real-time demo</span>
      </header>

      <section className="metrics-row">
        <div className="primary-metric-card">
          <div>
            <div className="primary-label">Current Price</div>
            <div className="primary-price">
              {quote
                ? `$${formatNumber(quote.price, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}`
                : '—'}
            </div>
          </div>
          <div className="primary-sub">
            {quote?.timestamp
              ? `Latest trading day: ${quote.timestamp}`
              : 'Waiting for first tick…'}
          </div>
        </div>

        <div className="secondary-metrics-grid">
          <div className="metric-card">
            <div className="metric-label">Day High</div>
            <div className="metric-value">
              {quote
                ? `$${formatNumber(quote.high, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}`
                : '—'}
            </div>
            <div className="metric-footnote">as reported by yfinance</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Day Low</div>
            <div className="metric-value">
              {quote
                ? `$${formatNumber(quote.low, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}`
                : '—'}
            </div>
            <div className="metric-footnote">session intraday low</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Volume</div>
            <div className="metric-value">
              {quote ? formatNumber(quote.volume) : '—'}
            </div>
            <div className="metric-footnote">shares traded today</div>
          </div>
        </div>
      </section>

      {sessionContext && (
        <section className="session-context-card">
          <div className="session-context-title">Session context (5m profile)</div>
          <div className="session-context-grid">
            <div className="session-block">
              <div className="session-block-label">Tail opportunity</div>
              {sessionContext.current_tail_opportunity?.type ? (
                <div className="tail-opportunity-alert">
                  <span className="tail-opp-type">
                    {sessionContext.current_tail_opportunity.type === 'buying_tail'
                      ? 'Buying tail'
                      : 'Selling tail'}
                  </span>
                  {' at '}
                  <span className="tail-opp-price">
                    ${formatNumber(sessionContext.current_tail_opportunity.price, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </span>
                  {sessionContext.current_tail_opportunity.distance_from_current_price != null && (
                    <>
                      {' · '}
                      <span className="tail-opp-distance">
                        {sessionContext.current_tail_opportunity.distance_from_current_price >= 0 ? '+' : ''}
                        {formatNumber(sessionContext.current_tail_opportunity.distance_from_current_price, {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}{' '}
                        from current
                      </span>
                    </>
                  )}
                  {sessionContext.current_tail_opportunity.reversion_target != null && (
                    <>
                      {' · reversion target POC '}
                      <span className="tail-opp-poc">
                        ${formatNumber(sessionContext.current_tail_opportunity.reversion_target, {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}
                      </span>
                    </>
                  )}
                  {sessionContext.current_tail_opportunity.confidence != null && (
                    <span className="tail-opp-confidence">
                      {' '}(confidence {formatNumber(sessionContext.current_tail_opportunity.confidence, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })})
                    </span>
                  )}
                </div>
              ) : (
                <div className="session-muted">No tail opportunity</div>
              )}
            </div>
            <div className="session-block">
              <div className="session-block-label">POC / value area</div>
              {sessionContext.session_stats?.poc != null ? (
                <div className="session-stats-line">
                  POC ${formatNumber(sessionContext.session_stats.poc, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  {' · VA '}
                  ${formatNumber(sessionContext.session_stats.value_area_low, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  {' – '}
                  ${formatNumber(sessionContext.session_stats.value_area_high, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
              ) : (
                <div className="session-muted">—</div>
              )}
            </div>
            <div className="session-block">
              <div className="session-block-label">Initial balance (first hour)</div>
              {sessionContext.initial_balance?.high != null ? (
                <div className="session-stats-line">
                  ${formatNumber(sessionContext.initial_balance.low, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  {' – '}
                  ${formatNumber(sessionContext.initial_balance.high, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  {' · range '}
                  {formatNumber(sessionContext.initial_balance.range, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
              ) : (
                <div className="session-muted">—</div>
              )}
            </div>
            <div className="session-block">
              <div className="session-block-label">Extensions beyond IB</div>
              {sessionContext.extensions ? (
                <div className="session-stats-line">
                  {sessionContext.extensions.above_ib ? (
                    <span className="ext-above">Above IB</span>
                  ) : (
                    <span className="session-muted">Not above IB</span>
                  )}
                  {' · '}
                  {sessionContext.extensions.below_ib ? (
                    <span className="ext-below">Below IB</span>
                  ) : (
                    <span className="session-muted">Not below IB</span>
                  )}
                </div>
              ) : (
                <div className="session-muted">—</div>
              )}
            </div>
            <div className="session-block session-block-full">
              <div className="session-block-label">Previous session (yesterday)</div>
              {sessionContext.previous_session?.poc != null ? (
                <div className="session-stats-line">
                  POC ${formatNumber(sessionContext.previous_session.poc, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  {' · VA '}
                  ${formatNumber(sessionContext.previous_session.value_area_low, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  {' – '}
                  ${formatNumber(sessionContext.previous_session.value_area_high, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  {sessionContext.previous_session.tails?.length > 0 && (
                    <> · {sessionContext.previous_session.tails.length} tail(s)</>
                  )}
                </div>
              ) : (
                <div className="session-muted">—</div>
              )}
            </div>
          </div>
        </section>
      )}

      <section className="chart-card">
        <div className="chart-header">
          <div>
            <div className="chart-title">30-minute TSLA bars</div>
            <div className="chart-subtitle">
              Latest {history.length} bars (30m candles) from yfinance
            </div>
          </div>
          {currentTail && currentTail.type && (
            <div
              className={
                currentTail.type === 'buying_tail'
                  ? 'tail-badge tail-buy'
                  : 'tail-badge tail-sell'
              }
            >
              <span className="tail-label">
                {currentTail.type === 'buying_tail'
                  ? 'Buying tail'
                  : 'Selling tail'}
              </span>
              <span className="tail-value">
                @{` $${formatNumber(currentTail.price, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}`}
              </span>
              {typeof currentTail.distance_from_poc === 'number' && (
                <span className="tail-distance">
                  {currentTail.distance_from_poc > 0 ? ' +' : ' '}
                  {formatNumber(Math.abs(currentTail.distance_from_poc), {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
                  {' vs POC'}
                </span>
              )}
            </div>
          )}
        </div>

        <PriceChart data={history} />

        <div className="status-row">
          <div
            className={
              error ? 'status-error' : quote ? 'status-live' : 'status-muted'
            }
          >
            <span className="status-dot" />
            <span>{statusLabel}</span>
          </div>
          <div>
            <span>Last updated: </span>
            <span className={error ? 'error-text' : ''}>
              {error || lastUpdatedLabel}
            </span>
          </div>
        </div>
      </section>
    </div>
  )
}

export default App

